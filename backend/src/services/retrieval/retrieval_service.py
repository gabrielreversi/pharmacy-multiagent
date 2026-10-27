from infra.qdrant.qdrant_repository import QdrantRepository
from services.embedding.embedding_service import EmbeddingService
from services.retrieval.config import RetrievalConfig
from services.retrieval.schemas import RetrievedChunk


class RetrievalService():
    def __init__(self, config: RetrievalConfig, embeddings: EmbeddingService, repository: QdrantRepository):
        self.config = config
        self.embeddings = embeddings
        self.repository = repository

    @classmethod
    def from_env(cls) -> "RetrievalService":
        return cls(RetrievalConfig.from_env(), EmbeddingService.from_env(), QdrantRepository.from_env())

    def retrieve(self, query: str, top_k: int | None = None, score_threshold: float | None = None) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("A query não pode ser vazia")

        vector = self.embeddings.embed_query(query)
        points = self.repository.search(
            vector,
            top_k=top_k or self.config.top_k,
            score_threshold=score_threshold if score_threshold is not None else self.config.score_threshold,
        )

        chunks = []
        for point in points:
            payload = dict(point.payload or {})
            content = payload.pop("content", None)
            chunks.append(RetrievedChunk(id=str(point.id), score=point.score, content=content, metadata=payload))
        return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)
