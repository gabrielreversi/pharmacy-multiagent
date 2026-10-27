from dataclasses import dataclass

from core.env import optional, required


@dataclass(frozen=True)
class EmbeddingConfig:
    azure_api_key: str
    azure_endpoint: str
    azure_api_version: str
    deployment: str
    dimensions: int
    batch_size: int

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            azure_api_key=required("OPENAI_API_KEY"),
            azure_endpoint=required("AZURE_OPENAI_ENDPOINT"),
            azure_api_version=required("AZURE_OPENAI_API_VERSION"),
            deployment=required("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            dimensions=int(optional("EMBEDDING_DIMENSIONS", "1536")),
            batch_size=int(optional("EMBEDDING_BATCH_SIZE", "64")),
        )
