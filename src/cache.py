"""
Query Caching and Optimization Module
Provides in-memory caching with TTL for expensive database queries
"""

import time
import threading
import logging
from typing import Any, Dict, Optional, Callable
from functools import wraps
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    value: Any
    timestamp: float
    ttl: float
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


class QueryCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    Features:
    - Configurable TTL per key or global default
    - Automatic cleanup of expired entries
    - Hit/miss statistics
    - Thread-safe operations
    """
    
    def __init__(self, default_ttl: float = 30.0, max_size: int = 1000, cleanup_interval: float = 60.0):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of entries
            cleanup_interval: How often to run cleanup (seconds)
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"QueryCache initialized: ttl={default_ttl}s, max_size={max_size}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.hits += 1
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        with self._lock:
            # Evict if at max size
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl
            )
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: String pattern to match (simple contains check)
            
        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            
            if keys_to_delete:
                logger.debug(f"Invalidated {len(keys_to_delete)} keys matching '{pattern}'")
            
            return len(keys_to_delete)
    
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        """
        Get from cache or compute and cache the value.
        
        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def _evict_oldest(self) -> None:
        """Evict oldest entry to make room."""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    def _cleanup_loop(self) -> None:
        """Background thread to clean up expired entries."""
        while True:
            time.sleep(self.cleanup_interval)
            self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate, 2),
                'default_ttl': self.default_ttl
            }


def cached(cache: QueryCache, key_prefix: str = '', ttl: Optional[float] = None):
    """
    Decorator for caching function results.
    
    Args:
        cache: QueryCache instance
        key_prefix: Prefix for cache keys
        ttl: Time-to-live in seconds
        
    Example:
        @cached(cache, 'deployment_metrics', ttl=30)
        def get_deployment_metrics(deployment: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ':'.join(key_parts)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


# Global cache instance
_global_cache: Optional[QueryCache] = None


def get_cache() -> QueryCache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = QueryCache(
            default_ttl=30.0,
            max_size=500,
            cleanup_interval=60.0
        )
    return _global_cache


def invalidate_deployment_cache(deployment: str) -> None:
    """Invalidate all cache entries for a deployment."""
    cache = get_cache()
    cache.invalidate_pattern(deployment)
