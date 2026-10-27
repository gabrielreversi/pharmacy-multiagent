import logging
import uuid
from collections import Counter
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from infra.database.models import Document, DocumentStatus
from infra.database.repositories import DocumentRepository
from infra.database.session import create_session_factory
from infra.queue.redis_stream import IngestionQueue
from infra.storage.blob_storage import BlobStorage
from services.ingestion.config import IngestionConfig
from services.ingestion.upload_service import IncomingFile, InvalidUploadError, UploadResult, UploadService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


class DocumentResponse(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    filename: str
    size_bytes: int
    status: str
    stage: str | None
    attempts: int
    error_code: str | None
    error_message: str | None
    page_count: int | None
    pdf_author: str | None
    pdf_creator: str | None
    pdf_created_at: str | None
    pdf_modified_at: str | None
    chunk_count: int | None
    embedding_model: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, document: Document) -> "DocumentResponse":
        return cls.model_validate(document, from_attributes=True)


class UploadStatusResponse(BaseModel):
    upload_id: uuid.UUID
    uploaded_by: str | None
    total_files: int
    created_at: datetime
    totals: dict[str, int]
    documents: list[DocumentResponse]


class FileResultResponse(BaseModel):
    filename: str
    status: str
    document_id: str | None = None
    reason: str | None = None


class UploadResponse(BaseModel):
    upload_id: str
    files: list[FileResultResponse]

    @classmethod
    def from_result(cls, result: UploadResult) -> "UploadResponse":
        return cls(upload_id=result.upload_id, files=[FileResultResponse(**vars(item)) for item in result.files])


@lru_cache
def _repository() -> DocumentRepository:
    return DocumentRepository(create_session_factory())


@lru_cache
def _upload_service() -> UploadService:
    return UploadService(_repository(), BlobStorage.from_env(), IngestionQueue.from_env(), IngestionConfig.from_env())


def get_repository() -> DocumentRepository:
    try:
        return _repository()
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Ingestão não configurada: {exc}") from exc


def get_upload_service() -> UploadService:
    try:
        return _upload_service()
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Ingestão não configurada: {exc}") from exc


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED, response_model=UploadResponse)
async def upload_documents(
    files: Annotated[
        list[UploadFile],
        File(
            description="Bulas em PDF",
            json_schema_extra={"items": {"type": "string", "format": "binary"}},
        ),
    ],
    service: Annotated[UploadService, Depends(get_upload_service)],
    uploaded_by: Annotated[str | None, Form()] = None,
):
    if len(files) > service.config.upload_max_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Máximo de {service.config.upload_max_files} arquivos por upload")

    incoming = []
    for upload in files:
        data = await upload.read(service.config.upload_max_file_bytes + 1)
        incoming.append(IncomingFile(filename=upload.filename or "documento.pdf", data=data))

    try:
        result = await run_in_threadpool(service.upload, incoming, uploaded_by)
    except InvalidUploadError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return UploadResponse.from_result(result)


@router.get("/uploads/{upload_id}", response_model=UploadStatusResponse)
def get_upload(upload_id: uuid.UUID, repository: Annotated[DocumentRepository, Depends(get_repository)]):
    found = repository.get_upload(upload_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload não encontrado")
    upload, documents = found
    counts = Counter(document.status for document in documents)
    return UploadStatusResponse(
        upload_id=upload.id,
        uploaded_by=upload.uploaded_by,
        total_files=upload.total_files,
        created_at=upload.created_at,
        totals={state.value: counts.get(state.value, 0) for state in DocumentStatus},
        documents=[DocumentResponse.from_model(document) for document in documents],
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, repository: Annotated[DocumentRepository, Depends(get_repository)]):
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    return DocumentResponse.from_model(document)


@router.post("/documents/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
def reprocess_document(
    document_id: uuid.UUID,
    service: Annotated[UploadService, Depends(get_upload_service)],
):
    document = service.repository.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    if not service.reprocess(document_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Só documentos com status 'failed' podem ser reprocessados (atual: {document.status})")
    return DocumentResponse.from_model(service.repository.get(document_id))
