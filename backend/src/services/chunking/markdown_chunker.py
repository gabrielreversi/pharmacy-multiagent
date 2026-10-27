import re
from dataclasses import asdict, dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from services.chunking.config import ChunkingConfig

PAGE_MARKER_RE = re.compile(r"<!--page:(\d+)-->")
HEADER_LINE_RE = re.compile(r"^#{1,6}\s+(.*)$")
NUMBERED_SECTION_RE = re.compile(r"^\d+\.\s")


@dataclass
class Chunk:
    index: int
    content: str
    embedding_text: str
    header: str | None
    section: str | None
    page_start: int
    page_end: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        return cls(**data)


@dataclass
class _Piece:
    text: str
    header: str | None
    section: str | None
    page_start: int
    page_end: int


class MarkdownChunker():
    def __init__(self, config: ChunkingConfig):
        self.config = config
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[(header, header) for header in config.headers],
            strip_headers=False,
        )
        self.size_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.max_chars,
            chunk_overlap=config.overlap_chars,
            add_start_index=True,
        )

    @classmethod
    def from_env(cls) -> "MarkdownChunker":
        return cls(ChunkingConfig.from_env())

    def chunk(self, markdown: str) -> list[Chunk]:
        pieces = self._split(markdown)
        pieces = self._merge_small(pieces)
        return [self._to_chunk(index, piece) for index, piece in enumerate(pieces)]

    def _split(self, markdown: str) -> list[_Piece]:
        pieces: list[_Piece] = []
        current_page = 1
        section: str | None = None

        for document in self.header_splitter.split_text(markdown):
            text = document.page_content.replace("  \n", "\n")
            header = self._header_of(text)
            if header and NUMBERED_SECTION_RE.match(header):
                section = header

            sub_texts = [(text, 0)] if len(text) <= self.config.max_chars else [
                (doc.page_content, doc.metadata["start_index"]) for doc in self.size_splitter.create_documents([text])
            ]
            for sub_text, start_index in sub_texts:
                start_page = self._page_at(text, start_index, current_page)
                page_start, page_end = self._page_span(sub_text, start_page)
                content = self._clean(sub_text)
                if content:
                    pieces.append(_Piece(content, header, section, page_start, page_end))

            current_page = self._page_at(text, len(text), current_page)

        return pieces

    def _merge_small(self, pieces: list[_Piece]) -> list[_Piece]:
        merged: list[_Piece] = []
        carry: _Piece | None = None
        for piece in pieces:
            if carry is not None:
                if carry.section == piece.section:
                    piece = _Piece(
                        text=f"{carry.text}\n\n{piece.text}",
                        header=piece.header,
                        section=piece.section,
                        page_start=carry.page_start,
                        page_end=piece.page_end,
                    )
                else:
                    merged.append(carry)
                carry = None
            if len(piece.text) < self.config.min_chars:
                carry = piece
            else:
                merged.append(piece)

        if carry is not None:
            if merged and merged[-1].section == carry.section:
                last = merged[-1]
                merged[-1] = _Piece(
                    text=f"{last.text}\n\n{carry.text}",
                    header=last.header,
                    section=last.section,
                    page_start=last.page_start,
                    page_end=carry.page_end,
                )
            else:
                merged.append(carry)
        return merged

    @staticmethod
    def _to_chunk(index: int, piece: _Piece) -> Chunk:
        context = []
        if piece.section and piece.section != piece.header:
            context.append(piece.section)
        if piece.header and not piece.text.startswith("#"):
            context.append(piece.header)
        prefix = " — ".join(context)
        embedding_text = f"{prefix}\n{piece.text}" if prefix else piece.text
        return Chunk(
            index=index,
            content=piece.text,
            embedding_text=embedding_text,
            header=piece.header,
            section=piece.section,
            page_start=piece.page_start,
            page_end=piece.page_end,
        )

    @staticmethod
    def _header_of(text: str) -> str | None:
        first_line = text.lstrip().split("\n", 1)[0]
        match = HEADER_LINE_RE.match(first_line)
        if not match:
            return None
        header = match.group(1).replace("**", "").strip()
        return re.sub(r"\s+", " ", header) or None

    @staticmethod
    def _page_at(text: str, position: int, start_page: int) -> int:
        page = start_page
        for match in PAGE_MARKER_RE.finditer(text):
            if match.start() >= position:
                break
            page = int(match.group(1))
        return page

    @staticmethod
    def _page_span(text: str, start_page: int) -> tuple[int, int]:
        pages: list[int] = []
        page = start_page
        last_end = 0
        for match in PAGE_MARKER_RE.finditer(text):
            if text[last_end:match.start()].strip():
                pages.append(page)
            page = int(match.group(1))
            last_end = match.end()
        if text[last_end:].strip():
            pages.append(page)
        if not pages:
            return page, page
        return min(pages), max(pages)

    @staticmethod
    def _clean(text: str) -> str:
        text = PAGE_MARKER_RE.sub("", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
