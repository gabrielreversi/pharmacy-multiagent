from dataclasses import dataclass

from core.env import optional


@dataclass(frozen=True)
class IngestionConfig:
    max_attempts: int
    upload_max_file_bytes: int
    upload_max_files: int

    @classmethod
    def from_env(cls) -> "IngestionConfig":
        return cls(
            max_attempts=int(optional("INGESTION_MAX_ATTEMPTS", "3")),
            upload_max_file_bytes=int(optional("UPLOAD_MAX_FILE_MB", "20")) * 1024 * 1024,
            upload_max_files=int(optional("UPLOAD_MAX_FILES", "10")),
        )
