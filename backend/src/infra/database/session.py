from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from infra.database.config import DatabaseConfig


def create_session_factory(config: DatabaseConfig | None = None) -> sessionmaker[Session]:
    engine = create_db_engine(config or DatabaseConfig.from_env())
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_db_engine(config: DatabaseConfig) -> Engine:
    return create_engine(config.url, pool_pre_ping=True)
