import logging

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from infra.storage.config import BlobStorageConfig

logger = logging.getLogger(__name__)


class BlobNotFoundError(Exception):
    pass


class BlobStorage():
    def __init__(self, config: BlobStorageConfig):
        service = BlobServiceClient.from_connection_string(config.connection_string)
        self.container = service.get_container_client(config.container)

    @classmethod
    def from_env(cls) -> "BlobStorage":
        return cls(BlobStorageConfig.from_env())

    def ensure_container(self) -> None:
        try:
            self.container.create_container()
            logger.info("Container '%s' criado no blob storage", self.container.container_name)
        except ResourceExistsError:
            pass

    def upload_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.container.upload_blob(
            name=path,
            data=data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    def download_bytes(self, path: str) -> bytes:
        try:
            return self.container.download_blob(path).readall()
        except ResourceNotFoundError as exc:
            raise BlobNotFoundError(path) from exc

    def upload_text(self, path: str, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        self.upload_bytes(path, text.encode("utf-8"), content_type)

    def download_text(self, path: str) -> str:
        return self.download_bytes(path).decode("utf-8")
