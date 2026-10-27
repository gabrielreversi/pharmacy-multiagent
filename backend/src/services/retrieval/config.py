from dataclasses import dataclass

from core.env import optional


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    score_threshold: float

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        return cls(
            top_k=int(optional("RETRIEVAL_TOP_K", "5")),
            score_threshold=float(optional("RETRIEVAL_SCORE_THRESHOLD", "0.0")),
        )
