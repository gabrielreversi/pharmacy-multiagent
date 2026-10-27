from dataclasses import dataclass

from core.env import optional, required


@dataclass(frozen=True)
class QueueConfig:
    redis_url: str
    stream: str
    dead_stream: str
    group: str
    claim_idle_ms: int

    @classmethod
    def from_env(cls) -> "QueueConfig":
        return cls(
            redis_url=required("REDIS_URL"),
            stream=optional("INGESTION_STREAM", "ingestion:documents"),
            dead_stream=optional("INGESTION_DEAD_STREAM", "ingestion:dead"),
            group=optional("INGESTION_GROUP", "ingestion-workers"),
            claim_idle_ms=int(optional("INGESTION_CLAIM_IDLE_MS", "60000")),
        )
