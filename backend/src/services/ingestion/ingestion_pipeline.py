import json
import logging
import uuid

from qdrant_client import models

from infra.database.models import Document, DocumentStage
from infra.database.repositories import DocumentRepository
from infra.qdrant.qdrant_repository import QdrantRepository
from infra.storage.blob_storage import BlobNotFoundError, BlobStorage
from services.chunking.markdown_chunker import Chunk, MarkdownChunker
from services.embedding.embedding_service import EmbeddingService
from services.extraction.pdf_extractor import NoTextError, extract
from services.ingestion.errors import PermanentError

logger = logging.getLogger(__name__)


def content_path(document_id: uuid.UUID) -> str:
    return f"processed/{document_id}/content.md"


def chunks_path(document_id: uuid.UUID) -> str:
    return f"processed/{document_id}/chunks.json"


def point_id(document_id: uuid.UUID, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{chunk_index}"))


class IngestionPipeline():
    def __init__(
        self,
        repository: DocumentRepository,
        storage: BlobStorage,
        chunker: MarkdownChunker,
        embeddings: EmbeddingService,
        vector_store: QdrantRepository,
    ):
        self.repository = repository
        self.storage = storage
        self.chunker = chunker
        self.embeddings = embeddings
        self.vector_store = vector_store

    def process(self, document: Document) -> None:
        stage = document.stage
        markdown: str | None = None
        chunks: list[Chunk] | None = None

        if stage is None:
            markdown = self._extract(document)
            stage = DocumentStage.EXTRACTED

        if stage == DocumentStage.EXTRACTED:
            if markdown is None:
                markdown = self._load_markdown(document)
            chunks = self._chunk(document, markdown)
            stage = DocumentStage.CHUNKED

        if chunks is None:
            chunks = self._load_chunks(document)
        self._index(document, chunks)

    def _extract(self, document: Document) -> str:
        try:
            data = self.storage.download_bytes(document.blob_path)
        except BlobNotFoundError as exc:
            raise PermanentError("SOURCE_NOT_FOUND", f"PDF não encontrado no blob: {document.blob_path}") from exc

        try:
            result = extract(data)
        except NoTextError as exc:
            raise PermanentError("NO_TEXT", str(exc)) from exc
        except Exception as exc:
            raise PermanentError("EXTRACTION_FAILED", f"{type(exc).__name__}: {exc}") from exc

        self.storage.upload_text(content_path(document.id), result.markdown, content_type="text/markdown; charset=utf-8")
        self.repository.set_stage(
            document.id,
            DocumentStage.EXTRACTED,
            page_count=result.page_count,
            pdf_author=result.metadata.get("author"),
            pdf_creator=result.metadata.get("creator"),
            pdf_created_at=result.metadata.get("created_at"),
            pdf_modified_at=result.metadata.get("modified_at"),
        )
        logger.info("Documento %s extraído (%s páginas)", document.id, result.page_count)
        return result.markdown

    def _chunk(self, document: Document, markdown: str) -> list[Chunk]:
        chunks = self.chunker.chunk(markdown)
        if not chunks:
            raise PermanentError("NO_CHUNKS", "Nenhum chunk gerado a partir do conteúdo extraído")

        payload = json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False)
        self.storage.upload_text(chunks_path(document.id), payload, content_type="application/json; charset=utf-8")
        self.repository.set_stage(document.id, DocumentStage.CHUNKED, chunk_count=len(chunks))
        logger.info("Documento %s dividido em %s chunks", document.id, len(chunks))
        return chunks

    def _index(self, document: Document, chunks: list[Chunk]) -> None:
        vectors = self.embeddings.embed_documents([chunk.embedding_text for chunk in chunks])
        points = [
            models.PointStruct(
                id=point_id(document.id, chunk.index),
                vector=vector,
                payload={
                    "content": chunk.content,
                    "document_id": str(document.id),
                    "chunk_index": chunk.index,
                    "header": chunk.header,
                    "section": chunk.section,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "filename": document.filename,
                    "embedding_model": self.embeddings.model_name,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        self.vector_store.delete_by_document(str(document.id))
        self.vector_store.upsert(points)
        self.repository.mark_indexed(document.id, chunk_count=len(points), embedding_model=self.embeddings.model_name)
        logger.info("Documento %s indexado com %s pontos", document.id, len(points))

    def _load_markdown(self, document: Document) -> str:
        try:
            return self.storage.download_text(content_path(document.id))
        except BlobNotFoundError:
            logger.warning("content.md ausente para %s; extraindo de novo", document.id)
            return self._extract(document)

    def _load_chunks(self, document: Document) -> list[Chunk]:
        try:
            raw = self.storage.download_text(chunks_path(document.id))
        except BlobNotFoundError:
            logger.warning("chunks.json ausente para %s; refazendo o chunking", document.id)
            return self._chunk(document, self._load_markdown(document))
        return [Chunk.from_dict(item) for item in json.loads(raw)]
