"""
Tests for cache module
"""
import pytest
import time
from unittest.mock import Mock


class TestQueryCache:
    """Test QueryCache functionality"""
    
    def test_cache_import(self):
        """Test QueryCache can be imported"""
        from src.cache import QueryCache
        assert QueryCache is not None
    
    def test_cache_initialization(self):
        """Test cache initializes correctly"""
        from src.cache import QueryCache
        
        cache = QueryCache(default_ttl=30.0, max_size=100)
        
        assert cache.default_ttl == 30.0
        assert cache.max_size == 100
    
    def test_set_and_get(self):
        """Test basic set and get operations"""
        from src.cache import QueryCache
        
        cache = QueryCache(default_ttl=60.0)
        
        cache.set('test_key', 'test_value')
        result = cache.get('test_key')
        
        assert result == 'test_value'
    
    def test_get_nonexistent(self):
        """Test getting nonexistent key returns None"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        result = cache.get('nonexistent')
        
        assert result is None
    
    def test_ttl_expiration(self):
        """Test that entries expire after TTL"""
        from src.cache import QueryCache
        
        cache = QueryCache(default_ttl=0.1)  # 100ms TTL
        
        cache.set('test_key', 'test_value')
        
        # Should exist immediately
        assert cache.get('test_key') == 'test_value'
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        assert cache.get('test_key') is None
    
    def test_custom_ttl(self):
        """Test custom TTL per key"""
        from src.cache import QueryCache
        
        cache = QueryCache(default_ttl=60.0)
        
        cache.set('short_ttl', 'value', ttl=0.1)
        cache.set('long_ttl', 'value', ttl=60.0)
        
        time.sleep(0.15)
        
        assert cache.get('short_ttl') is None
        assert cache.get('long_ttl') == 'value'
    
    def test_delete(self):
        """Test deleting a key"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        cache.set('test_key', 'test_value')
        assert cache.get('test_key') == 'test_value'
        
        result = cache.delete('test_key')
        
        assert result is True
        assert cache.get('test_key') is None
    
    def test_delete_nonexistent(self):
        """Test deleting nonexistent key"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        result = cache.delete('nonexistent')
        
        assert result is False
    
    def test_clear(self):
        """Test clearing all entries"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        cache.clear()
        
        assert cache.get('key1') is None
        assert cache.get('key2') is None
    
    def test_invalidate_pattern(self):
        """Test invalidating keys by pattern"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        cache.set('deployment:app1:metrics', 'value1')
        cache.set('deployment:app1:cost', 'value2')
        cache.set('deployment:app2:metrics', 'value3')
        
        count = cache.invalidate_pattern('app1')
        
        assert count == 2
        assert cache.get('deployment:app1:metrics') is None
        assert cache.get('deployment:app1:cost') is None
        assert cache.get('deployment:app2:metrics') == 'value3'
    
    def test_get_or_set(self):
        """Test get_or_set functionality"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        call_count = 0
        def factory():
            nonlocal call_count
            call_count += 1
            return 'computed_value'
        
        # First call should compute
        result1 = cache.get_or_set('test_key', factory)
        assert result1 == 'computed_value'
        assert call_count == 1
        
        # Second call should use cache
        result2 = cache.get_or_set('test_key', factory)
        assert result2 == 'computed_value'
        assert call_count == 1  # Factory not called again
    
    def test_stats(self):
        """Test cache statistics"""
        from src.cache import QueryCache
        
        cache = QueryCache()
        
        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('key1')  # Hit
        cache.get('nonexistent')  # Miss
        
        stats = cache.stats
        
        assert stats['size'] == 1
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['hit_rate'] > 0


class TestCacheDecorator:
    """Test cached decorator"""
    
    def test_cached_decorator(self):
        """Test cached decorator works"""
        from src.cache import QueryCache, cached
        
        cache = QueryCache()
        call_count = 0
        
        @cached(cache, 'test_func')
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call with same args - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1
        
        # Different args - should compute
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2


class TestGlobalCache:
    """Test global cache functions"""
    
    def test_get_cache(self):
        """Test getting global cache instance"""
        from src.cache import get_cache
        
        cache1 = get_cache()
        cache2 = get_cache()
        
        # Should return same instance
        assert cache1 is cache2
    
    def test_invalidate_deployment_cache(self):
        """Test invalidating deployment cache"""
        from src.cache import get_cache, invalidate_deployment_cache
        
        cache = get_cache()
        cache.set('deployment:test-app:metrics', 'value')
        
        invalidate_deployment_cache('test-app')
        
        assert cache.get('deployment:test-app:metrics') is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
