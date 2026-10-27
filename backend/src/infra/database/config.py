from dataclasses import dataclass

from core.env import required


@dataclass(frozen=True)
class DatabaseConfig:
    url: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(url=required("DATABASE_URL"))
