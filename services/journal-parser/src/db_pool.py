"""
PLOS - Database Connection Pooling & Performance Optimization
Production-grade connection management and query optimization
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# DATABASE CONNECTION POOL
# ============================================================================


class DatabaseConnectionPool:
    """
    Production-grade async database connection pooling

    Per architecture:
    - Connection pool: 5-20 connections
    - Connection reuse (don't create new each time)
    - Automatic reconnection on failure
    - Query timeout handling
    - Performance monitoring
    """

    def __init__(
        self,
        database_url: str,
        min_connections: int = 5,
        max_connections: int = 20,
        pool_recycle: int = 3600,  # Recycle connections after 1 hour
        pool_pre_ping: bool = True,  # Check connections before use
        echo: bool = False,  # Set True for SQL logging in dev
    ):
        """
        Initialize connection pool

        Args:
            database_url: PostgreSQL connection string
            min_connections: Minimum pool size
            max_connections: Maximum pool size
            pool_recycle: Seconds before recycling connection
            pool_pre_ping: Test connection before use
            echo: Enable SQL echo (dev only)
        """
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

        # Pool configuration
        self.pool_config = {
            "poolclass": QueuePool,
            "pool_size": min_connections,
            "max_overflow": max_connections - min_connections,
            "pool_recycle": pool_recycle,
            "pool_pre_ping": pool_pre_ping,
            "pool_timeout": 30,  # Wait up to 30 seconds for connection
            "echo": echo,
            "echo_pool": False,  # Set True to debug pool
        }

        self.database_url = database_url
        self._is_initialized = False

        # Metrics
        self.queries_executed = 0
        self.total_query_time_ms = 0
        self.connection_errors = 0

    async def initialize(self) -> None:
        """Initialize engine and session factory"""
        if self._is_initialized:
            logger.warning("Database pool already initialized")
            return

        logger.info("Initializing database connection pool")

        try:
            # Create async engine with pooling
            self.engine = create_async_engine(self.database_url, **self.pool_config)

            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,  # Don't expire objects after commit
                autoflush=False,  # Manual flush for control
                autocommit=False,
            )

            # Register event listeners
            self._register_events()

            # Test connection
            async with self.get_session() as session:
                await session.execute("SELECT 1")

            self._is_initialized = True
            logger.info(
                f"Database pool initialized: "
                f"pool_size={self.pool_config['pool_size']}, "
                f"max_overflow={self.pool_config['max_overflow']}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close all connections and dispose engine"""
        if not self._is_initialized:
            return

        logger.info("Closing database connection pool")

        if self.engine:
            await self.engine.dispose()

        self._is_initialized = False
        logger.info("Database pool closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session from pool

        Usage:
        async with pool.get_session() as session:
            result = await session.execute(query)
        """
        if not self._is_initialized:
            raise RuntimeError(
                "Database pool not initialized. Call initialize() first."
            )

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Session error, rolled back: {e}")
                raise
            finally:
                await session.close()

    def _register_events(self) -> None:
        """Register SQLAlchemy event listeners for monitoring"""

        @event.listens_for(self.engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Called on new connection"""
            logger.debug("New database connection established")

        @event.listens_for(self.engine.sync_engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Called when connection checked out from pool"""
            self.queries_executed += 1

        @event.listens_for(self.engine.sync_engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Called when connection returned to pool"""
            pass

        @event.listens_for(self.engine.sync_engine, "close")
        def receive_close(dbapi_conn, connection_record):
            """Called when connection closed"""
            logger.debug("Database connection closed")

        @event.listens_for(self.engine.sync_engine, "connect")
        def set_connection_timeout(dbapi_conn, connection_record):
            """Set statement timeout for safety"""
            cursor = dbapi_conn.cursor()
            # Timeout queries after 30 seconds
            cursor.execute("SET statement_timeout = '30s'")
            cursor.close()

    def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status"""
        if not self.engine:
            return {"status": "not_initialized"}

        pool = self.engine.pool

        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_queries": self.queries_executed,
            "connection_errors": self.connection_errors,
            "avg_query_time_ms": (
                self.total_query_time_ms / self.queries_executed
                if self.queries_executed > 0
                else 0
            ),
        }


# ============================================================================
# QUERY OPTIMIZER
# ============================================================================


class QueryOptimizer:
    """
    Query optimization utilities

    Per architecture:
    - Query parallelization (asyncio.gather)
    - Materialized view usage
    - Index hints
    - Query result caching
    """

    @staticmethod
    async def parallel_queries(*queries) -> tuple:
        """
        Execute multiple queries in parallel

        Don't do: query1(100ms) + query2(100ms) = 200ms
        Do this: asyncio.gather(query1, query2) = 100ms

        Usage:
        result1, result2 = await parallel_queries(
            session.execute(query1),
            session.execute(query2)
        )
        """
        return await asyncio.gather(*queries)

    @staticmethod
    async def parallel_with_timeout(*queries, timeout: float = 5.0) -> tuple:
        """
        Execute queries in parallel with timeout

        Graceful degradation: If query times out, return None
        """
        try:
            return await asyncio.wait_for(
                asyncio.gather(*queries, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Queries timed out after {timeout}s")
            return tuple(None for _ in queries)

    @staticmethod
    def use_materialized_view(user_id: str, view_type: str) -> str:
        """
        Generate query using materialized view

        Available views:
        - mv_user_7day_context: Last 7 days aggregates
        - mv_user_30day_baseline: 30-day baseline with day-of-week patterns
        """
        if view_type == "7day":
            return f"""
                SELECT * FROM mv_user_7day_context
                WHERE user_id = '{user_id}'
            """
        elif view_type == "30day":
            return f"""
                SELECT * FROM mv_user_30day_baseline
                WHERE user_id = '{user_id}'
            """
        else:
            raise ValueError(f"Unknown view type: {view_type}")

    @staticmethod
    def optimize_journal_query(user_id: str, days: int = 7) -> str:
        """
        Optimized query for recent journal entries
        Uses indexes: idx_journal_user_date
        """
        return f"""
            SELECT
                id, entry_date, extracted_data,
                relationship_state, sleep_debt_cumulative
            FROM journal_extractions
            WHERE user_id = '{user_id}'
              AND entry_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY entry_date DESC
            LIMIT {days}
        """


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================


class PerformanceMonitor:
    """Monitor query performance"""

    def __init__(self):
        self.slow_queries = []
        self.query_counts = {}

    async def monitor_query(self, query_name: str, query_func):
        """Monitor query execution time"""
        import time

        start = time.time()
        try:
            result = await query_func
            elapsed_ms = (time.time() - start) * 1000

            # Log slow queries
            if elapsed_ms > 1000:  # > 1 second
                logger.warning(
                    f"Slow query detected: {query_name} took {elapsed_ms:.0f}ms"
                )
                self.slow_queries.append(
                    {
                        "query": query_name,
                        "duration_ms": elapsed_ms,
                        "timestamp": time.time(),
                    }
                )

            # Track query counts
            self.query_counts[query_name] = self.query_counts.get(query_name, 0) + 1

            return result

        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"Query failed: {query_name} after {elapsed_ms:.0f}ms - {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "slow_queries_count": len(self.slow_queries),
            "query_counts": self.query_counts,
            "recent_slow_queries": self.slow_queries[-10:],  # Last 10
        }


# ============================================================================
# GLOBAL POOL INSTANCE
# ============================================================================

# Global connection pool (initialized at startup)
_global_pool: Optional[DatabaseConnectionPool] = None


def get_global_pool() -> DatabaseConnectionPool:
    """Get global database pool"""
    if _global_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _global_pool


async def initialize_global_pool(database_url: str) -> None:
    """Initialize global database pool"""
    global _global_pool

    _global_pool = DatabaseConnectionPool(database_url)
    await _global_pool.initialize()


async def close_global_pool() -> None:
    """Close global database pool"""
    global _global_pool

    if _global_pool:
        await _global_pool.close()
        _global_pool = None
