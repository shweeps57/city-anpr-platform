"""Consume perception plate events from Redis Streams and persist them."""

import asyncio
import json
import logging
import os

from pydantic import ValidationError
from redis.exceptions import ResponseError

from database.connection import get_db_connection, get_redis
from models.schemas import PlateEventCreate
from services.alerts import check_blacklist, create_alert
from services.realtime import alert_hub


logger = logging.getLogger(__name__)

STREAM_NAME = os.getenv("REDIS_STREAM", "plate-events")
CONSUMER_GROUP = os.getenv("REDIS_CONSUMER_GROUP", "backend-events")
CONSUMER_NAME = os.getenv("REDIS_CONSUMER_NAME", "backend-api")
FAILED_STREAM_NAME = f"{STREAM_NAME}:failed"


def decode_event(fields: dict[str, str]) -> PlateEventCreate:
    """Decode Redis field values, which the perception worker JSON-serializes."""
    decoded: dict[str, object] = {}
    for key, value in fields.items():
        if value == "":
            decoded[key] = None
            continue
        try:
            decoded[key] = json.loads(value)
        except json.JSONDecodeError:
            decoded[key] = value

    return PlateEventCreate.model_validate(decoded)


def persist_event(event: PlateEventCreate) -> bool:
    """Insert an event once and derive its PostGIS location from its camera."""
    values = event.model_dump()
    values["plate_number"] = event.plate_number.upper()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plate_events (
                    event_id, plate_number, confidence, camera_id, timestamp,
                    vehicle_type, direction, track_id, location, snapshot_path
                )
                SELECT
                    %(event_id)s, %(plate_number)s, %(confidence)s,
                    %(camera_id)s::varchar(50),
                    %(timestamp)s, %(vehicle_type)s, %(direction)s, %(track_id)s,
                    ST_SetSRID(ST_MakePoint(c.longitude, c.latitude), 4326),
                    %(snapshot_path)s
                FROM cameras c
                WHERE c.camera_id = %(camera_id)s::varchar(50)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                values,
            )
            inserted = cur.fetchone() is not None
        conn.commit()

    if not inserted:
        logger.info("Duplicate event ignored: %s", event.event_id)
    return inserted


def create_blacklist_alert(event: PlateEventCreate) -> dict | None:
    """Create an alert only when this newly stored event matches the blacklist."""
    entry = check_blacklist(event.plate_number)
    if entry is None:
        return None

    reason = entry.get("reason")
    message = f"Blacklisted vehicle {event.plate_number.upper()} detected at {event.camera_id}"
    if reason:
        message += f": {reason}"

    return create_alert(
        plate_number=event.plate_number,
        alert_type="blacklist",
        message=message,
        camera_id=event.camera_id,
    )


class PlateEventConsumer:
    """Reliable Redis Stream consumer run in the FastAPI application lifecycle."""

    def __init__(self) -> None:
        self._redis = get_redis()
        self._stopping = asyncio.Event()

    async def run(self) -> None:
        try:
            await self._redis.xgroup_create(
                STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True
            )
            logger.info("Created Redis consumer group %s", CONSUMER_GROUP)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        logger.info("Consuming Redis stream %s", STREAM_NAME)
        while not self._stopping.is_set():
            messages = await self._redis.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_NAME: ">"},
                count=10,
                block=1000,
            )
            for _, entries in messages:
                for message_id, fields in entries:
                    await self._process(message_id, fields)

    async def stop(self) -> None:
        self._stopping.set()

    async def _process(self, message_id: str, fields: dict[str, str]) -> None:
        try:
            event = decode_event(fields)
            inserted = await asyncio.to_thread(persist_event, event)
            if inserted:
                alert = await asyncio.to_thread(create_blacklist_alert, event)
                if alert:
                    await alert_hub.broadcast(alert)
            await self._redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
        except (ValidationError, ValueError, TypeError) as exc:
            await self._move_to_failed_stream(message_id, fields, str(exc))
        except Exception as exc:
            logger.exception("Could not process Redis event %s", message_id)
            await self._move_to_failed_stream(message_id, fields, str(exc))

    async def _move_to_failed_stream(
        self, message_id: str, fields: dict[str, str], error: str
    ) -> None:
        """Preserve invalid events for diagnosis instead of retrying forever."""
        await self._redis.xadd(
            FAILED_STREAM_NAME,
            {
                "source_message_id": message_id,
                "error": error,
                "payload": json.dumps(fields),
            },
        )
        await self._redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
        logger.warning("Moved invalid event %s to %s", message_id, FAILED_STREAM_NAME)
