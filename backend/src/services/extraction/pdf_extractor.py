import logging
from dataclasses import dataclass, field

import pymupdf
import pymupdf4llm

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
PAGE_MARKER = "<!--page:{page}-->"
MIN_TEXT_CHARS = 200


class InvalidPdfError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class NoTextError(Exception):
    pass


@dataclass(frozen=True)
class PdfInfo:
    page_count: int


@dataclass
class ExtractionResult:
    markdown: str
    page_count: int
    metadata: dict[str, str | None] = field(default_factory=dict)


def validate_pdf(data: bytes) -> PdfInfo:
    if not data.startswith(PDF_MAGIC):
        raise InvalidPdfError("O arquivo não é um PDF (assinatura %PDF ausente)")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise InvalidPdfError(f"PDF corrompido ou ilegível: {exc}") from exc
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise InvalidPdfError("PDF protegido por senha")
        if doc.page_count < 1:
            raise InvalidPdfError("PDF sem páginas")
        return PdfInfo(page_count=doc.page_count)


def extract(data: bytes) -> ExtractionResult:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        text_chars = sum(len(page.get_text().strip()) for page in doc)
        if text_chars < MIN_TEXT_CHARS:
            raise NoTextError(f"PDF sem texto extraível ({text_chars} caracteres); provavelmente escaneado")

        pages = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)
        parts = []
        for number, page in enumerate(pages, start=1):
            page_number = page.get("metadata", {}).get("page_number", number)
            parts.append(f"{PAGE_MARKER.format(page=page_number)}\n{page['text'].strip()}")

        raw_metadata = doc.metadata or {}
        metadata = {
            "author": raw_metadata.get("author") or None,
            "creator": raw_metadata.get("creator") or raw_metadata.get("producer") or None,
            "created_at": raw_metadata.get("creationDate") or None,
            "modified_at": raw_metadata.get("modDate") or None,
            "title": raw_metadata.get("title") or None,
        }
        return ExtractionResult(markdown="\n\n".join(parts) + "\n", page_count=doc.page_count, metadata=metadata)
