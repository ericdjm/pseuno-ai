"""
Rate limiting implementations.
Uses Redis when REDIS_URL is set, otherwise falls back to in-memory storage.
"""

import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Protocol

from redis import Redis

from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Return True if the rate limit is exceeded."""


class InMemoryRateLimiter:
    """In-memory rate limiter with LRU cleanup."""

    def __init__(self, max_size: int = 10000):
        self.store: OrderedDict[str, dict] = OrderedDict()
        self.max_size = max_size
        self._lock = Lock()

    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        current_time = time.time()
        with self._lock:
            if len(self.store) > self.max_size:
                for _ in range(self.max_size // 5):
                    self.store.popitem(last=False)

            if key not in self.store:
                self.store[key] = {"count": 1, "window_start": current_time}
                return False

            rate_data = self.store[key]

            if current_time - rate_data["window_start"] > window:
                rate_data["count"] = 1
                rate_data["window_start"] = current_time
                return False

            rate_data["count"] += 1
            self.store.move_to_end(key)
            return rate_data["count"] > limit


class RedisRateLimiter:
    """Redis-backed rate limiter using INCR + EXPIRE."""

    def __init__(self, redis_url: str, key_prefix: str = "pseuno:rate:"):
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        redis_key = self._key(key)
        count = self._redis.incr(redis_key)
        if count == 1:
            self._redis.expire(redis_key, window)
        return count > limit


def create_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.redis_url:
        logger.info("Rate limiter using Redis backend")
        return RedisRateLimiter(settings.redis_url)
    logger.warning("Rate limiter using in-memory backend")
    return InMemoryRateLimiter()
