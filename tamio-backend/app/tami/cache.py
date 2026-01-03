"""Simple in-memory cache for TAMI context.

This provides a TTL-based cache to avoid rebuilding expensive context
payloads on every message in a conversation.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """A cached context entry with expiration."""
    data: Any
    expires_at: datetime


class ContextCache:
    """
    Simple in-memory cache for TAMI context payloads.

    Cache key is user_id + active_scenario_id.
    Default TTL is 60 seconds (conversations are usually quick).
    """

    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def _make_key(self, user_id: str, scenario_id: Optional[str] = None) -> str:
        """Generate cache key."""
        return f"{user_id}:{scenario_id or 'base'}"

    def get(self, user_id: str, scenario_id: Optional[str] = None) -> Optional[Any]:
        """Get cached context if not expired."""
        key = self._make_key(user_id, scenario_id)
        entry = self._cache.get(key)

        if entry is None:
            return None

        if datetime.utcnow() > entry.expires_at:
            # Expired, remove from cache
            del self._cache[key]
            return None

        return entry.data

    def set(self, user_id: str, data: Any, scenario_id: Optional[str] = None) -> None:
        """Cache context data with TTL."""
        key = self._make_key(user_id, scenario_id)
        self._cache[key] = CacheEntry(
            data=data,
            expires_at=datetime.utcnow() + self._ttl
        )

    def invalidate(self, user_id: str, scenario_id: Optional[str] = None) -> None:
        """Invalidate cache for a user."""
        key = self._make_key(user_id, scenario_id)
        if key in self._cache:
            del self._cache[key]

    def invalidate_user(self, user_id: str) -> None:
        """Invalidate all cache entries for a user."""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self._cache[key]

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()


# Global cache instance with 60 second TTL
context_cache = ContextCache(ttl_seconds=60)
