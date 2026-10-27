import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Literal

from infra.database.models import Document, DocumentStatus
from infra.database.repositories import DocumentRepository, DuplicateDocumentError
from infra.queue.redis_stream import IngestionQueue
from infra.storage.blob_storage import BlobStorage
from services.extraction.pdf_extractor import InvalidPdfError, validate_pdf
from services.ingestion.config import IngestionConfig

logger = logging.getLogger(__name__)


class InvalidUploadError(ValueError):
    pass


@dataclass(frozen=True)
class IncomingFile:
    filename: str
    data: bytes


@dataclass
class FileResult:
    filename: str
    status: Literal["accepted", "rejected", "duplicate"]
    document_id: str | None = None
    reason: str | None = None


@dataclass
class UploadResult:
    upload_id: str
    files: list[FileResult] = field(default_factory=list)


def raw_blob_path(document_id: uuid.UUID, filename: str) -> str:
    return f"raw/{document_id}/{filename}"


def safe_filename(filename: str) -> str:
    name = PurePath(filename or "documento.pdf").name
    name = re.sub(r"[^\w.\- ]", "_", name).strip() or "documento.pdf"
    return name[:200]


class UploadService():
    def __init__(self, repository: DocumentRepository, storage: BlobStorage, queue: IngestionQueue, config: IngestionConfig):
        self.repository = repository
        self.storage = storage
        self.queue = queue
        self.config = config

    def upload(self, files: list[IncomingFile], uploaded_by: str | None) -> UploadResult:
        if not files:
            raise InvalidUploadError("Nenhum arquivo enviado")
        if len(files) > self.config.upload_max_files:
            raise InvalidUploadError(f"Máximo de {self.config.upload_max_files} arquivos por upload")

        upload = self.repository.create_upload(uploaded_by=uploaded_by, total_files=len(files))
        result = UploadResult(upload_id=str(upload.id))
        for incoming in files:
            result.files.append(self._handle_file(upload.id, incoming))
        return result

    def reprocess(self, document_id: uuid.UUID) -> bool:
        if not self.repository.requeue_failed(document_id):
            return False
        self.queue.publish(str(document_id))
        return True

    def _handle_file(self, upload_id: uuid.UUID, incoming: IncomingFile) -> FileResult:
        filename = safe_filename(incoming.filename)

        if len(incoming.data) > self.config.upload_max_file_bytes:
            limit_mb = self.config.upload_max_file_bytes // (1024 * 1024)
            return FileResult(filename, "rejected", reason=f"Arquivo maior que {limit_mb} MB")
        try:
            info = validate_pdf(incoming.data)
        except InvalidPdfError as exc:
            return FileResult(filename, "rejected", reason=exc.reason)

        content_hash = hashlib.sha256(incoming.data).hexdigest()
        existing = self.repository.get_by_hash(content_hash)
        if existing is not None:
            return FileResult(filename, "duplicate", document_id=str(existing.id), reason="Arquivo já enviado anteriormente")

        document_id = uuid.uuid4()
        document = Document(
            id=document_id,
            upload_id=upload_id,
            filename=filename,
            size_bytes=len(incoming.data),
            content_hash=content_hash,
            blob_path=raw_blob_path(document_id, filename),
            status=DocumentStatus.QUEUED,
            attempts=0,
            page_count=info.page_count,
        )
        try:
            self.repository.create_document(document)
        except DuplicateDocumentError:
            existing = self.repository.get_by_hash(content_hash)
            return FileResult(filename, "duplicate", document_id=str(existing.id) if existing else None, reason="Arquivo já enviado anteriormente")

        try:
            self.storage.upload_bytes(document.blob_path, incoming.data, content_type="application/pdf")
        except Exception:
            logger.exception("Falha ao gravar %s no blob storage", document.blob_path)
            self.repository.delete(document_id)
            return FileResult(filename, "rejected", reason="Falha ao armazenar o arquivo; tente novamente")

        try:
            self.queue.publish(str(document_id))
        except Exception:
            logger.exception("Falha ao publicar o documento %s na fila; a reconciliação do worker vai reenviar", document_id)

        return FileResult(filename, "accepted", document_id=str(document_id))
