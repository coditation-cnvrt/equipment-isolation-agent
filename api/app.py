"""FastAPI application factory."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import CnvrtAuthMiddleware
from api.db import PostgresRunRepository, auto_init_schema_on_startup, init_schema, postgres_config_from_env
from api.routes import router
from api.runs import RunStore
from pipeline.env import load_dotenv


def create_app() -> FastAPI:
    load_dotenv()
    max_workers = int(os.environ.get("EIA_MAX_CONCURRENT_RUNS") or "2")
    run_timeout = int(os.environ.get("EIA_RUN_TIMEOUT_SECONDS") or "900")
    pg_config = postgres_config_from_env()
    if not pg_config.configured:
        raise RuntimeError("PostgreSQL is required; configure POSTGRES_HOST, POSTGRES_DB, and POSTGRES_USER")
    repository = PostgresRunRepository(pg_config)
    run_store = RunStore(max_workers=max_workers, run_timeout_seconds=run_timeout, repository=repository)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            if auto_init_schema_on_startup():
                init_schema(pg_config)
            repository.check_ready()
            yield
        finally:
            run_store.shutdown()

    app = FastAPI(title="Equipment Isolation Agent API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CnvrtAuthMiddleware)
    origins = [
        item.strip()
        for item in os.environ.get("EIA_CORS_ORIGINS", "http://localhost:5173").split(",")
        if item.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.state.run_store = run_store
    app.include_router(router)
    return app


app = create_app()
