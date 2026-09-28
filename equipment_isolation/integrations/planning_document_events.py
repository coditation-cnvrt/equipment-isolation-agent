"""Durable UniGraph planning-document event consumer."""
from __future__ import annotations

import logging
import os

from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin

from equipment_isolation.api.db import PostgresRunRepository
from equipment_isolation.api.database import postgres_config_from_env
from equipment_isolation.pipeline.env import load_dotenv


LOGGER = logging.getLogger(__name__)
EXCHANGE_NAME = "unigraph.events"
ROUTING_PATTERN = "unigraph.graph.updated.*"
DEFAULT_QUEUE = "equipment-isolation.planning-input-events.v1"


class PlanningDocumentEventWorker(ConsumerMixin):
    def __init__(self, connection: Connection, repository: PostgresRunRepository, *, source_id: str, queue_name: str):
        self.connection = connection
        self.repository = repository
        self.source_id = source_id.rstrip("/")
        exchange = Exchange(EXCHANGE_NAME, type="topic", durable=True)
        self.queue = Queue(
            queue_name,
            exchange=exchange,
            routing_key=ROUTING_PATTERN,
            durable=True,
            exclusive=False,
            auto_delete=False,
        )

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(
                queues=[self.queue],
                callbacks=[self.on_message],
                accept=["json"],
                prefetch_count=1,
            )
        ]

    def on_message(self, body, message) -> None:
        try:
            result = self.repository.apply_planning_document_event(body, source_id=self.source_id)
        except Exception:
            LOGGER.exception("Planning-document event persistence failed; delivery will be retried")
            message.reject(requeue=True)
            return
        message.ack()
        LOGGER.info(
            "Planning-document event %s %s%s",
            result["event_id"],
            result["status"],
            " (duplicate)" if result["duplicate"] else "",
        )


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    broker_url = str(os.environ.get("EIA_UNIGRAPH_EVENTS_BROKER_URL") or "").strip()
    source_id = str(os.environ.get("UNIGRAPH_API_BASE_URL") or "").strip()
    if not broker_url:
        raise RuntimeError("EIA_UNIGRAPH_EVENTS_BROKER_URL is required")
    if not source_id:
        raise RuntimeError("UNIGRAPH_API_BASE_URL is required")
    repository = PostgresRunRepository(postgres_config_from_env())
    repository.check_ready()
    try:
        with Connection(
            broker_url,
            connect_timeout=5,
            transport_options={"confirm_publish": True},
        ) as connection:
            PlanningDocumentEventWorker(
                connection,
                repository,
                source_id=source_id,
                queue_name=str(os.environ.get("EIA_UNIGRAPH_EVENTS_QUEUE") or DEFAULT_QUEUE),
            ).run()
    finally:
        repository.close()


if __name__ == "__main__":
    main()
