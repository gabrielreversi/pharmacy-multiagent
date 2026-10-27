import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from infra.database.models import Document, DocumentStage, DocumentStatus, Upload


class DuplicateDocumentError(Exception):
    pass


class DocumentRepository():
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_upload(self, uploaded_by: str | None, total_files: int) -> Upload:
        with self.session_factory.begin() as session:
            upload = Upload(uploaded_by=uploaded_by, total_files=total_files)
            session.add(upload)
        return upload

    def get_upload(self, upload_id: uuid.UUID) -> tuple[Upload, list[Document]] | None:
        with self.session_factory() as session:
            upload = session.get(Upload, upload_id)
            if upload is None:
                return None
            documents = session.scalars(
                select(Document).where(Document.upload_id == upload_id).order_by(Document.created_at)
            ).all()
            return upload, list(documents)

    def get_by_hash(self, content_hash: str) -> Document | None:
        with self.session_factory() as session:
            return session.scalar(select(Document).where(Document.content_hash == content_hash))

    def get(self, document_id: uuid.UUID) -> Document | None:
        with self.session_factory() as session:
            return session.get(Document, document_id)

    def create_document(self, document: Document) -> Document:
        try:
            with self.session_factory.begin() as session:
                session.add(document)
        except IntegrityError as exc:
            raise DuplicateDocumentError(document.content_hash) from exc
        return document

    def delete(self, document_id: uuid.UUID) -> None:
        with self.session_factory.begin() as session:
            document = session.get(Document, document_id)
            if document is not None:
                session.delete(document)

    def start_attempt(self, document_id: uuid.UUID) -> Document | None:
        with self.session_factory.begin() as session:
            document = session.get(Document, document_id, with_for_update=True)
            if document is None or document.status in (DocumentStatus.INDEXED, DocumentStatus.FAILED):
                return document
            document.status = DocumentStatus.PROCESSING
            document.attempts += 1
            document.error_code = None
            document.error_message = None
        return document

    def update_fields(self, document_id: uuid.UUID, **fields) -> None:
        with self.session_factory.begin() as session:
            session.execute(update(Document).where(Document.id == document_id).values(**fields))

    def set_stage(self, document_id: uuid.UUID, stage: DocumentStage, **fields) -> None:
        self.update_fields(document_id, stage=stage, **fields)

    def mark_indexed(self, document_id: uuid.UUID, chunk_count: int, embedding_model: str) -> None:
        self.update_fields(
            document_id,
            stage=DocumentStage.INDEXED,
            status=DocumentStatus.INDEXED,
            chunk_count=chunk_count,
            embedding_model=embedding_model,
            error_code=None,
            error_message=None,
        )

    def mark_failed(self, document_id: uuid.UUID, error_code: str, error_message: str) -> None:
        self.update_fields(
            document_id,
            status=DocumentStatus.FAILED,
            error_code=error_code,
            error_message=error_message[:2000],
        )

    def mark_retry_pending(self, document_id: uuid.UUID, error_code: str, error_message: str) -> None:
        self.update_fields(
            document_id,
            status=DocumentStatus.QUEUED,
            error_code=error_code,
            error_message=error_message[:2000],
        )

    def requeue_failed(self, document_id: uuid.UUID) -> bool:
        with self.session_factory.begin() as session:
            result = session.execute(
                update(Document)
                .where(Document.id == document_id, Document.status == DocumentStatus.FAILED)
                .values(status=DocumentStatus.QUEUED, attempts=0, error_code=None, error_message=None)
            )
            return result.rowcount == 1

    def find_stale(self, older_than: timedelta) -> list[uuid.UUID]:
        cutoff = datetime.now(timezone.utc) - older_than
        with self.session_factory() as session:
            return list(session.scalars(
                select(Document.id).where(
                    Document.status.in_([DocumentStatus.QUEUED, DocumentStatus.PROCESSING]),
                    Document.updated_at < cutoff,
                )
            ).all())

    def touch(self, document_ids: list[uuid.UUID]) -> None:
        if not document_ids:
            return
        with self.session_factory.begin() as session:
            session.execute(update(Document).where(Document.id.in_(document_ids)).values(updated_at=datetime.now(timezone.utc)))
