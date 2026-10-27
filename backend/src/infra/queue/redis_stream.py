import logging
from dataclasses import dataclass

import redis

from infra.queue.config import QueueConfig

logger = logging.getLogger(__name__)

STREAM_MAXLEN = 10_000


@dataclass(frozen=True)
class QueueMessage:
    message_id: str
    document_id: str


class IngestionQueue():
    def __init__(self, config: QueueConfig):
        self.config = config
        self.client = redis.Redis.from_url(config.redis_url, decode_responses=True, socket_timeout=15)

    @classmethod
    def from_env(cls) -> "IngestionQueue":
        return cls(QueueConfig.from_env())

    def ensure_group(self) -> None:
        try:
            self.client.xgroup_create(self.config.stream, self.config.group, id="0", mkstream=True)
            logger.info("Consumer group '%s' criado no stream '%s'", self.config.group, self.config.stream)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, document_id: str) -> str:
        return self.client.xadd(
            self.config.stream,
            {"document_id": document_id},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )

    def read(self, consumer: str, block_ms: int = 5000, count: int = 1) -> list[QueueMessage]:
        response = self.client.xreadgroup(
            self.config.group,
            consumer,
            streams={self.config.stream: ">"},
            count=count,
            block=block_ms,
        )
        return self._parse_read(response)

    def autoclaim(self, consumer: str, count: int = 10) -> list[QueueMessage]:
        response = self.client.xautoclaim(
            self.config.stream,
            self.config.group,
            consumer,
            min_idle_time=self.config.claim_idle_ms,
            start_id="0-0",
            count=count,
        )
        return self._to_messages(response[1])

    def ack(self, message_id: str) -> None:
        self.client.xack(self.config.stream, self.config.group, message_id)

    def dead_letter(self, message: QueueMessage, error_code: str, error_message: str) -> None:
        self.client.xadd(
            self.config.dead_stream,
            {
                "document_id": message.document_id,
                "original_id": message.message_id,
                "error_code": error_code,
                "error_message": error_message[:1000],
            },
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )

    def _parse_read(self, response) -> list[QueueMessage]:
        if not response:
            return []
        if isinstance(response, dict):
            entries = [entry for stream_entries in response.values() for entry in stream_entries[0]]
            return self._to_messages(entries)
        return self._to_messages([entry for _, stream_entries in response for entry in stream_entries])

    @staticmethod
    def _to_messages(entries) -> list[QueueMessage]:
        messages = []
        for message_id, fields in entries:
            if not fields or "document_id" not in fields:
                continue
            messages.append(QueueMessage(message_id=message_id, document_id=fields["document_id"]))
        return messages
