"""
Unit tests for cache service.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from src.services.cache_service import CacheService


@pytest.fixture
def cache_service():
    """Create a cache service instance for testing."""
    service = CacheService()
    return service


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = Mock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = True
    mock.keys.return_value = []
    mock.dbsize.return_value = 0
    mock.info.return_value = {
        'used_memory_human': '1M',
        'keyspace_hits': 100,
        'keyspace_misses': 50
    }
    return mock


class TestCacheService:
    """Test cases for CacheService."""

    def test_initialization(self, cache_service):
        """Test cache service initialization."""
        assert cache_service.client is None
        assert cache_service._connected is False

    @patch('redis.from_url')
    def test_connect_success(self, mock_from_url, cache_service, mock_redis):
        """Test successful connection to Redis."""
        mock_from_url.return_value = mock_redis

        result = cache_service.connect()

        assert result is True
        assert cache_service._connected is True
        assert cache_service.client is not None
        mock_redis.ping.assert_called_once()

    @patch('redis.from_url')
    def test_connect_failure(self, mock_from_url, cache_service):
        """Test failed connection to Redis."""
        mock_from_url.side_effect = Exception("Connection failed")

        result = cache_service.connect()

        assert result is False
        assert cache_service._connected is False

    def test_is_connected(self, cache_service):
        """Test connection status check."""
        assert cache_service.is_connected() is False

        cache_service._connected = True
        assert cache_service.is_connected() is True

    @pytest.mark.asyncio
    async def test_get_article_not_connected(self, cache_service):
        """Test getting article when not connected."""
        result = await cache_service.get_article("test_id")
        assert result is None

    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_get_article_cache_hit(self, mock_from_url, cache_service, mock_redis):
        """Test getting article from cache (hit)."""
        import json

        article_data = {"id": "test_id", "title": "Test"}
        mock_redis.get.return_value = json.dumps(article_data)
        mock_from_url.return_value = mock_redis

        cache_service.connect()
        result = await cache_service.get_article("test_id")

        assert result == article_data
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_get_article_cache_miss(self, mock_from_url, cache_service, mock_redis):
        """Test getting article from cache (miss)."""
        mock_redis.get.return_value = None
        mock_from_url.return_value = mock_redis

        cache_service.connect()
        result = await cache_service.get_article("test_id")

        assert result is None

    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_set_article(self, mock_from_url, cache_service, mock_redis):
        """Test setting article in cache."""
        mock_from_url.return_value = mock_redis
        cache_service.connect()

        article_data = {"id": "test_id", "title": "Test"}
        result = await cache_service.set_article("test_id", article_data)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_delete_article(self, mock_from_url, cache_service, mock_redis):
        """Test deleting article from cache."""
        mock_from_url.return_value = mock_redis
        cache_service.connect()

        result = await cache_service.delete_article("test_id")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_invalidate_pattern(self, mock_from_url, cache_service, mock_redis):
        """Test invalidating cache by pattern."""
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_from_url.return_value = mock_redis
        cache_service.connect()

        await cache_service.invalidate_pattern("test:*")

        mock_redis.keys.assert_called_once_with("test:*")
        mock_redis.delete.assert_called_once_with("key1", "key2", "key3")

    @patch('redis.from_url')
    def test_get_cache_info(self, mock_from_url, cache_service, mock_redis):
        """Test getting cache statistics."""
        mock_from_url.return_value = mock_redis
        cache_service.connect()

        info = cache_service.get_cache_info()

        assert info['connected'] is True
        assert 'used_memory_human' in info
        assert 'hits' in info
        assert 'misses' in info
        assert 'hit_rate' in info

    def test_generate_cache_key(self, cache_service):
        """Test cache key generation."""
        key = cache_service._generate_cache_key("prefix:", "arg1", "arg2", param1="value1")

        assert key.startswith("prefix:")
        assert "arg1" in key
        assert "arg2" in key
        assert "param1=value1" in key

    def test_generate_cache_key_long(self, cache_service):
        """Test cache key generation for long keys."""
        # Generate a very long key
        long_args = ["arg" * 50 for _ in range(10)]
        key = cache_service._generate_cache_key("prefix:", *long_args)

        # Should be hashed
        assert "hash:" in key
        assert len(key) < 250  # Hashed keys should be shorter
