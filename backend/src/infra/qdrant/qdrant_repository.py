import logging
import time

from qdrant_client import QdrantClient, models

from infra.qdrant.config import QdrantConfig

logger = logging.getLogger(__name__)

KEYWORD_INDEXES = ("document_id",)


class CollectionConfigMismatchError(RuntimeError):
    pass


class QdrantRepository():
    def __init__(self, config: QdrantConfig):
        self.collection = config.collection
        self.dimensions = config.dimensions
        self.distance = models.Distance.COSINE
        self.client = QdrantClient(url=config.url, api_key=config.api_key, timeout=10)
        self.ready = False

    @classmethod
    def from_env(cls) -> "QdrantRepository":
        return cls(QdrantConfig.from_env())

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=self.dimensions, distance=self.distance),
            )
            logger.info("Collection '%s' criada (%s dims, %s)", self.collection, self.dimensions, self.distance.value)
        else:
            vectors = self.client.get_collection(self.collection).config.params.vectors
            if not isinstance(vectors, models.VectorParams) or vectors.size != self.dimensions or vectors.distance != self.distance:
                raise CollectionConfigMismatchError(
                    f"Collection '{self.collection}' existe com configuração {vectors}, "
                    f"mas o esperado é {self.dimensions} dims / {self.distance.value}. "
                    "Use outra collection ou reindexe."
                )
            logger.info("Collection '%s' já existe com a configuração esperada", self.collection)

        self.ensure_payload_indexes()
        self.ready = True

    def ensure_payload_indexes(self) -> None:
        existing = self.client.get_collection(self.collection).payload_schema or {}
        for field in KEYWORD_INDEXES:
            if field in existing:
                continue
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )
            logger.info("Payload index '%s' criado na collection '%s'", field, self.collection)

    def ensure_collection_with_retry(self, attempts: int = 10, interval: float = 2.0) -> bool:
        for attempt in range(1, attempts + 1):
            try:
                self.ensure_collection()
                return True
            except CollectionConfigMismatchError:
                raise
            except Exception as exc:
                logger.warning("Qdrant indisponível (tentativa %s/%s): %s", attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(interval)
        logger.error("Qdrant indisponível após %s tentativas; o RAG ficará indisponível até ele voltar", attempts)
        return False

    def search(self, vector: list[float], top_k: int, score_threshold: float | None = None) -> list[models.ScoredPoint]:
        if not self.ready:
            self.ensure_collection()
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return response.points

    def upsert(self, points: list[models.PointStruct]) -> None:
        if not self.ready:
            self.ensure_collection()
        self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def delete_by_document(self, document_id: str) -> None:
        if not self.ready:
            self.ensure_collection()
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
                )
            ),
            wait=True,
        )

    def count_by_document(self, document_id: str) -> int:
        result = self.client.count(
            collection_name=self.collection,
            count_filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            ),
            exact=True,
        )
        return result.count
