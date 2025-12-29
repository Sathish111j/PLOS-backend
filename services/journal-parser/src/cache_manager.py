"""
PLOS v2.0 - Multi-Layer Cache Manager
Implements Memory -> Redis -> PostgreSQL -> Defaults fallback strategy
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# IN-MEMORY CACHE (L1 - Fastest)
# ============================================================================

class MemoryCache:
    """
    In-process memory cache for fastest access
    TTL: 6 hours
    Size limit: 1000 users
    """
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 6):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from memory cache"""
        if key not in self._cache:
            self._misses += 1
            return None
        
        # Check TTL
        if datetime.utcnow() - self._timestamps[key] > self.ttl:
            self._evict(key)
            self._misses += 1
            return None
        
        self._hits += 1
        logger.debug(f"Memory cache HIT: {key}")
        return self._cache[key]
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Set in memory cache with TTL"""
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._timestamps, key=self._timestamps.get)
            self._evict(oldest_key)
        
        self._cache[key] = value
        self._timestamps[key] = datetime.utcnow()
        logger.debug(f"Memory cache SET: {key}")
    
    def _evict(self, key: str) -> None:
        """Remove key from cache"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def invalidate(self, pattern: str) -> None:
        """Invalidate all keys matching pattern"""
        keys_to_remove = [k for k in self._cache if pattern in k]
        for key in keys_to_remove:
            self._evict(key)
        logger.info(f"Invalidated {len(keys_to_remove)} keys matching '{pattern}'")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "size": len(self._cache),
            "max_size": self.max_size
        }


# ============================================================================
# MULTI-LAYER CACHE MANAGER
# ============================================================================

class MultiLayerCacheManager:
    """
    Implements 4-tier caching strategy:
    L1: Memory (< 1ms) - process RAM
    L2: Redis (10-20ms) - distributed cache
    L3: PostgreSQL (100-500ms) - source of truth
    L4: Defaults (< 1ms) - fallback values
    """
    
    def __init__(self, redis_client=None, db_session=None):
        self.memory = MemoryCache()
        self.redis = redis_client
        self.db = db_session
        
        # Default baselines (population averages)
        self.defaults = {
            "baseline": {
                "sleep_hours": 7.0,
                "sleep_quality": 6.5,
                "mood_score": 6.5,
                "energy_level": 6.0,
                "stress_level": 4.0,
                "productivity": 6.0,
                "confidence": 0.15
            },
            "patterns": {},
            "activity_impacts": {}
        }
    
    async def get_user_baseline(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get user baseline with fallback chain:
        Memory -> Redis -> PostgreSQL -> Defaults
        """
        key = f"baseline:{user_id}"
        
        # L1: Memory Cache
        cached = self.memory.get(key)
        if cached:
            logger.debug(f"L1 HIT: {key}")
            return cached
        
        # L2: Redis Cache
        if self.redis:
            try:
                redis_data = await asyncio.wait_for(
                    self._redis_get(key),
                    timeout=5.0  # 5 second timeout
                )
                if redis_data:
                    logger.debug(f"L2 HIT: {key}")
                    # Cache in memory for next time
                    self.memory.set(key, redis_data)
                    return redis_data
            except asyncio.TimeoutError:
                logger.warning(f"Redis timeout for {key}")
            except Exception as e:
                logger.warning(f"Redis error for {key}: {e}")
        
        # L3: PostgreSQL
        if self.db:
            try:
                db_data = await asyncio.wait_for(
                    self._db_get_baseline(user_id),
                    timeout=2.0  # 2 second timeout
                )
                if db_data:
                    logger.debug(f"L3 HIT: {key}")
                    # Cache in Redis and Memory
                    self.memory.set(key, db_data)
                    if self.redis:
                        await self._redis_set(key, db_data, ttl=3600)  # 1 hour
                    return db_data
            except asyncio.TimeoutError:
                logger.warning(f"Database timeout for {key}")
            except Exception as e:
                logger.warning(f"Database error for {key}: {e}")
        
        # L4: Defaults (always works)
        logger.info(f"Using default baseline for {user_id} (no data available)")
        return self.defaults["baseline"].copy()
    
    async def get_user_patterns(
        self,
        user_id: UUID,
        pattern_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user patterns with caching"""
        key = f"patterns:{user_id}"
        if pattern_type:
            key += f":{pattern_type}"
        
        # L1: Memory
        cached = self.memory.get(key)
        if cached:
            return cached
        
        # L2: Redis
        if self.redis:
            try:
                redis_data = await asyncio.wait_for(
                    self._redis_get(key),
                    timeout=5.0
                )
                if redis_data:
                    self.memory.set(key, redis_data)
                    return redis_data
            except:
                pass
        
        # L3: PostgreSQL
        if self.db:
            try:
                db_data = await asyncio.wait_for(
                    self._db_get_patterns(user_id, pattern_type),
                    timeout=2.0
                )
                if db_data:
                    self.memory.set(key, db_data)
                    if self.redis:
                        await self._redis_set(key, db_data, ttl=3600)
                    return db_data
            except:
                pass
        
        # L4: Defaults
        return {}
    
    async def get_activity_patterns(self, user_id: UUID) -> list:
        """Get activity patterns with caching"""
        key = f"activities:{user_id}"
        
        # L1: Memory
        cached = self.memory.get(key)
        if cached:
            return cached
        
        # L2: Redis
        if self.redis:
            try:
                redis_data = await asyncio.wait_for(
                    self._redis_get(key),
                    timeout=5.0
                )
                if redis_data:
                    self.memory.set(key, redis_data)
                    return redis_data
            except:
                pass
        
        # L3: PostgreSQL
        if self.db:
            try:
                db_data = await asyncio.wait_for(
                    self._db_get_activities(user_id),
                    timeout=2.0
                )
                if db_data:
                    self.memory.set(key, db_data)
                    if self.redis:
                        await self._redis_set(key, db_data, ttl=3600)
                    return db_data
            except:
                pass
        
        # L4: Empty list
        return []
    
    async def invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidate all cache layers for a user"""
        logger.info(f"Invalidating cache for user {user_id}")
        
        # Invalidate memory
        self.memory.invalidate(str(user_id))
        
        # Invalidate Redis
        if self.redis:
            try:
                await self._redis_delete_pattern(f"*:{user_id}*")
            except Exception as e:
                logger.warning(f"Redis invalidation error: {e}")
    
    # ========================================================================
    # REDIS OPERATIONS
    # ========================================================================
    
    async def _redis_get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from Redis with JSON deserialization"""
        if not self.redis:
            return None
        
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def _redis_set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        """Set in Redis with JSON serialization"""
        if not self.redis:
            return
        
        await self.redis.setex(
            key,
            ttl,
            json.dumps(value, default=str)
        )
    
    async def _redis_delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern"""
        if not self.redis:
            return
        
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    # ========================================================================
    # DATABASE OPERATIONS
    # ========================================================================
    
    async def _db_get_baseline(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get baseline from database"""
        # This would query user_patterns table
        # Implementation depends on your DB schema
        # For now, placeholder
        return None
    
    async def _db_get_patterns(
        self,
        user_id: UUID,
        pattern_type: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get patterns from database"""
        return None
    
    async def _db_get_activities(self, user_id: UUID) -> Optional[list]:
        """Get activity patterns from database"""
        return None
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            "memory": self.memory.get_stats(),
            "redis_connected": self.redis is not None,
            "db_connected": self.db is not None
        }
