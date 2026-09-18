import os
import psycopg
import psycopg.rows
import redis.asyncio as aioredis
from contextlib import asynccontextmanager

# Connection settings from environment variables with Docker defaults
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "host=postgres dbname=anpr user=anpr password=anpr_dev_password"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Global connection objects
_redis_client: aioredis.Redis | None = None


def get_db_connection():
    """Get a synchronous database connection with dict rows."""
    return psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)


def get_redis() -> aioredis.Redis:
    """Get or create the Redis async client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def close_connections():
    """Close all connections on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
