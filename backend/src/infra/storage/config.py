from dataclasses import dataclass

from core.env import required


@dataclass(frozen=True)
class BlobStorageConfig:
    connection_string: str
    container: str

    @classmethod
    def from_env(cls) -> "BlobStorageConfig":
        return cls(
            connection_string=required("AZURE_STORAGE_CONNECTION_STRING"),
            container=required("AZURE_STORAGE_CONTAINER"),
        )
