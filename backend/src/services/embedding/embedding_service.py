from langchain_openai import AzureOpenAIEmbeddings

from services.embedding.config import EmbeddingConfig


class EmbeddingService():
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model_name = config.deployment
        self.model = AzureOpenAIEmbeddings(
            api_key=config.azure_api_key,
            azure_endpoint=config.azure_endpoint,
            azure_deployment=config.deployment,
            api_version=config.azure_api_version,
            dimensions=config.dimensions,
            check_embedding_ctx_length=False,
            max_retries=3,
        )

    @classmethod
    def from_env(cls) -> "EmbeddingService":
        return cls(EmbeddingConfig.from_env())

    def embed_query(self, text: str) -> list[float]:
        return self.model.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            vectors.extend(self.model.embed_documents(texts[start:start + self.config.batch_size]))
        return vectors
