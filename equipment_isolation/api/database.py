"""Shared SQLAlchemy configuration for PostgreSQL persistence."""
from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    sslmode: str = "prefer"

    @property
    def configured(self) -> bool:
        return bool(self.host and self.dbname and self.user)


def postgres_config_from_env() -> PostgresConfig:
    return PostgresConfig(
        host=os.environ.get("POSTGRES_HOST", "").strip(),
        port=int(os.environ.get("POSTGRES_PORT") or "5432"),
        dbname=os.environ.get("POSTGRES_DB", "").strip(),
        user=os.environ.get("POSTGRES_USER", "").strip(),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer").strip() or "prefer",
    )


def postgres_configured() -> bool:
    return postgres_config_from_env().configured


def database_url(config: PostgresConfig | None = None) -> URL:
    pg = config or postgres_config_from_env()
    if not pg.configured:
        raise RuntimeError(
            "PostgreSQL is required; configure POSTGRES_HOST, POSTGRES_DB, and POSTGRES_USER"
        )
    return URL.create(
        "postgresql+psycopg",
        username=pg.user,
        password=pg.password,
        host=pg.host,
        port=pg.port,
        database=pg.dbname,
        query={"sslmode": pg.sslmode},
    )


def create_database_engine(config: PostgresConfig | None = None) -> Engine:
    return create_engine(
        database_url(config),
        pool_size=int(os.environ.get("POSTGRES_POOL_MAX_SIZE") or "8"),
        max_overflow=0,
        pool_timeout=float(os.environ.get("POSTGRES_POOL_TIMEOUT_SECONDS") or "5"),
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
