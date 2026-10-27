import logging
import os
import signal
import socket
import time
import uuid
from datetime import timedelta

from infra.database.models import DocumentStatus
from infra.database.repositories import DocumentRepository
from infra.database.session import create_session_factory
from infra.qdrant.qdrant_repository import QdrantRepository
from infra.queue.redis_stream import IngestionQueue, QueueMessage
from infra.storage.blob_storage import BlobStorage
from services.chunking.markdown_chunker import MarkdownChunker
from services.embedding.embedding_service import EmbeddingService
from services.ingestion.config import IngestionConfig
from services.ingestion.errors import classify
from services.ingestion.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger("workers.ingestion")

RECONCILE_INTERVAL_SECONDS = 60
STALE_AFTER = timedelta(minutes=10)
DEPENDENCY_RETRY_SECONDS = 5


class IngestionWorker():
    def __init__(
        self,
        queue: IngestionQueue,
        repository: DocumentRepository,
        pipeline: IngestionPipeline,
        vector_store: QdrantRepository,
        config: IngestionConfig,
        consumer: str,
    ):
        self.queue = queue
        self.repository = repository
        self.pipeline = pipeline
        self.vector_store = vector_store
        self.config = config
        self.consumer = consumer
        self.running = True
        self.last_reconcile = 0.0

    @classmethod
    def from_env(cls) -> "IngestionWorker":
        repository = DocumentRepository(create_session_factory())
        vector_store = QdrantRepository.from_env()
        pipeline = IngestionPipeline(
            repository=repository,
            storage=BlobStorage.from_env(),
            chunker=MarkdownChunker.from_env(),
            embeddings=EmbeddingService.from_env(),
            vector_store=vector_store,
        )
        consumer = os.getenv("INGESTION_CONSUMER") or f"worker-{socket.gethostname()}"
        return cls(IngestionQueue.from_env(), repository, pipeline, vector_store, IngestionConfig.from_env(), consumer)

    def stop(self, *_) -> None:
        logger.info("Sinal de parada recebido; finalizando após a mensagem atual")
        self.running = False

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self._wait_for_dependencies()
        logger.info("Worker '%s' escutando o stream '%s'", self.consumer, self.queue.config.stream)

        while self.running:
            try:
                self._maybe_reconcile()
                messages = self.queue.autoclaim(self.consumer) or self.queue.read(self.consumer)
            except Exception:
                logger.exception("Falha ao ler a fila; tentando de novo em %ss", DEPENDENCY_RETRY_SECONDS)
                time.sleep(DEPENDENCY_RETRY_SECONDS)
                continue
            for message in messages:
                self.handle(message)
                if not self.running:
                    break

    def handle(self, message: QueueMessage) -> None:
        try:
            document_id = uuid.UUID(message.document_id)
        except ValueError:
            logger.error("Mensagem %s com document_id inválido: %r", message.message_id, message.document_id)
            self.queue.ack(message.message_id)
            return

        try:
            document = self.repository.start_attempt(document_id)
        except Exception:
            logger.exception("Postgres indisponível ao iniciar %s; a mensagem será retomada", document_id)
            return

        if document is None:
            logger.warning("Documento %s não existe mais; descartando a mensagem", document_id)
            self.queue.ack(message.message_id)
            return
        if document.status in (DocumentStatus.INDEXED, DocumentStatus.FAILED):
            logger.info("Documento %s já está %s; confirmando a mensagem", document_id, document.status)
            self.queue.ack(message.message_id)
            return

        logger.info("Processando %s (%s), tentativa %s, etapa %s", document_id, document.filename, document.attempts, document.stage)
        try:
            self.pipeline.process(document)
            self.queue.ack(message.message_id)
        except Exception as exc:
            self._handle_failure(message, document_id, document.attempts, exc)

    def _handle_failure(self, message: QueueMessage, document_id: uuid.UUID, attempts: int, exc: Exception) -> None:
        error = classify(exc)
        try:
            if not error.transient:
                logger.error("Falha permanente em %s: %s", document_id, error)
                self.repository.mark_failed(document_id, error.code, error.message)
                self.queue.ack(message.message_id)
            elif attempts >= self.config.max_attempts:
                logger.error("Falha temporária em %s após %s tentativas; enviando para o dead-letter: %s", document_id, attempts, error)
                self.repository.mark_failed(document_id, error.code, error.message)
                self.queue.dead_letter(message, error.code, error.message)
                self.queue.ack(message.message_id)
            else:
                logger.warning(
                    "Falha temporária em %s (tentativa %s/%s): %s; nova tentativa em ~%ss",
                    document_id, attempts, self.config.max_attempts, error, self.queue.config.claim_idle_ms // 1000,
                )
                self.repository.mark_retry_pending(document_id, error.code, error.message)
        except Exception:
            logger.exception("Não foi possível registrar a falha de %s; a mensagem continua pendente", document_id)

    def _maybe_reconcile(self) -> None:
        if time.monotonic() - self.last_reconcile < RECONCILE_INTERVAL_SECONDS:
            return
        self.last_reconcile = time.monotonic()
        stale = self.repository.find_stale(STALE_AFTER)
        if not stale:
            return
        logger.warning("Reconciliação: republicando %s documento(s) parados", len(stale))
        for document_id in stale:
            self.queue.publish(str(document_id))
        self.repository.touch(stale)

    def _wait_for_dependencies(self) -> None:
        while self.running:
            try:
                self.queue.ensure_group()
                break
            except Exception as exc:
                logger.warning("Redis indisponível (%s); tentando de novo em %ss", exc, DEPENDENCY_RETRY_SECONDS)
                time.sleep(DEPENDENCY_RETRY_SECONDS)
        self.vector_store.ensure_collection_with_retry()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    IngestionWorker.from_env().run()


if __name__ == "__main__":
    main()
