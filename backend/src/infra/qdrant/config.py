from dataclasses import dataclass

from core.env import optional, required


@dataclass(frozen=True)
class QdrantConfig:
    url: str
    api_key: str | None
    collection: str
    dimensions: int

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        return cls(
            url=required("QDRANT_URL"),
            api_key=optional("QDRANT_API_KEY", "") or None,
            collection=required("QDRANT_COLLECTION"),
            dimensions=int(optional("EMBEDDING_DIMENSIONS", "1536")),
        )
