from dataclasses import dataclass

from core.env import optional


@dataclass(frozen=True)
class ChunkingConfig:
    headers: tuple[str, ...]
    max_chars: int
    overlap_chars: int
    min_chars: int

    @classmethod
    def from_env(cls) -> "ChunkingConfig":
        headers = tuple(h.strip() for h in optional("CHUNK_HEADER", "#####").split(",") if h.strip())
        return cls(
            headers=headers or ("#####",),
            max_chars=int(optional("CHUNK_MAX_CHARS", "4000")),
            overlap_chars=int(optional("CHUNK_OVERLAP_CHARS", "400")),
            min_chars=int(optional("CHUNK_MIN_CHARS", "200")),
        )
