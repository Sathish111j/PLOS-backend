import os
from typing import Optional
import asyncpg
from shared.utils.logger import get_logger

logger = get_logger(__name__)

class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def connect(cls):
        """Initialize database connection pool."""
        if cls._pool is None:
            try:
                dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
                if not dsn:
                    raise ValueError("DATABASE_URL or POSTGRES_URL not set")
                    
                cls._pool = await asyncpg.create_pool(
                    dsn=dsn,
                    min_size=int(os.getenv("DB_POOL_MIN", "2")),
                    max_size=int(os.getenv("DB_POOL_MAX", "10")),
                )
                logger.info("Database connection pool established")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise

    @classmethod
    async def disconnect(cls):
        """Close database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """Get the connection pool."""
        if cls._pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        return cls._pool

    @classmethod
    async def fetch_one(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetch_all(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def execute(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
