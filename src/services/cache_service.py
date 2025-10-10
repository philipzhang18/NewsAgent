"""
Redis cache service for reducing database queries and improving performance.
"""

import logging
import json
import hashlib
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import redis
from redis.exceptions import ConnectionError, TimeoutError

from ..models.news_models import NewsArticle, NewsCollection
from ..config.settings import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing Redis cache operations."""

    # Cache key prefixes
    PREFIX_ARTICLE = "article:"
    PREFIX_ARTICLES = "articles:"
    PREFIX_SEARCH = "search:"
    PREFIX_STATS = "stats:"
    PREFIX_COLLECTIONS = "collections:"
    PREFIX_SOURCES = "sources:"

    # Default TTL (time-to-live) in seconds
    TTL_ARTICLE = 3600  # 1 hour
    TTL_ARTICLES_LIST = 300  # 5 minutes
    TTL_SEARCH = 600  # 10 minutes
    TTL_STATS = 180  # 3 minutes
    TTL_COLLECTIONS = 600  # 10 minutes
    TTL_SOURCES = 1800  # 30 minutes

    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            logger.info(f"Connecting to Redis at {settings.REDIS_URL}")

            # Parse Redis URL
            self.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # Test connection
            self.client.ping()

            self._connected = True
            logger.info("Successfully connected to Redis")
            return True

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Error connecting to Redis: {str(e)}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key based on parameters."""
        # Create a string representation of all parameters
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])

        # Create a hash for long keys
        key_string = ":".join(key_parts)
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}hash:{key_hash}"

        return key_string

    # Article caching

    async def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get article from cache."""
        if not self.is_connected():
            return None

        try:
            key = self.PREFIX_ARTICLE + article_id
            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for article: {article_id}")
                return json.loads(data)
            logger.debug(f"Cache miss for article: {article_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting article from cache: {str(e)}")
            return None

    async def set_article(self, article_id: str, article_data: Dict[str, Any], ttl: int = TTL_ARTICLE) -> bool:
        """Set article in cache."""
        if not self.is_connected():
            return False

        try:
            key = self.PREFIX_ARTICLE + article_id
            self.client.setex(key, ttl, json.dumps(article_data))
            logger.debug(f"Cached article: {article_id}")
            return True

        except Exception as e:
            logger.error(f"Error setting article in cache: {str(e)}")
            return False

    async def delete_article(self, article_id: str) -> bool:
        """Delete article from cache."""
        if not self.is_connected():
            return False

        try:
            key = self.PREFIX_ARTICLE + article_id
            self.client.delete(key)
            logger.debug(f"Deleted article from cache: {article_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting article from cache: {str(e)}")
            return False

    # Articles list caching

    async def get_articles(
        self,
        limit: int = 50,
        skip: int = 0,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get articles list from cache."""
        if not self.is_connected():
            return None

        try:
            key = self._generate_cache_key(
                self.PREFIX_ARTICLES,
                limit=limit,
                skip=skip,
                source_name=source_name,
                category=category,
                sentiment=sentiment,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )

            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for articles list")
                return json.loads(data)
            logger.debug(f"Cache miss for articles list")
            return None

        except Exception as e:
            logger.error(f"Error getting articles list from cache: {str(e)}")
            return None

    async def set_articles(
        self,
        articles_data: List[Dict[str, Any]],
        limit: int = 50,
        skip: int = 0,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ttl: int = TTL_ARTICLES_LIST
    ) -> bool:
        """Set articles list in cache."""
        if not self.is_connected():
            return False

        try:
            key = self._generate_cache_key(
                self.PREFIX_ARTICLES,
                limit=limit,
                skip=skip,
                source_name=source_name,
                category=category,
                sentiment=sentiment,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )

            self.client.setex(key, ttl, json.dumps(articles_data))
            logger.debug(f"Cached articles list")
            return True

        except Exception as e:
            logger.error(f"Error setting articles list in cache: {str(e)}")
            return False

    # Search results caching

    async def get_search_results(self, query: str, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Get search results from cache."""
        if not self.is_connected():
            return None

        try:
            key = self._generate_cache_key(self.PREFIX_SEARCH, query, limit=limit)
            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for search: {query}")
                return json.loads(data)
            logger.debug(f"Cache miss for search: {query}")
            return None

        except Exception as e:
            logger.error(f"Error getting search results from cache: {str(e)}")
            return None

    async def set_search_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        limit: int = 50,
        ttl: int = TTL_SEARCH
    ) -> bool:
        """Set search results in cache."""
        if not self.is_connected():
            return False

        try:
            key = self._generate_cache_key(self.PREFIX_SEARCH, query, limit=limit)
            self.client.setex(key, ttl, json.dumps(results))
            logger.debug(f"Cached search results for: {query}")
            return True

        except Exception as e:
            logger.error(f"Error setting search results in cache: {str(e)}")
            return False

    # Statistics caching

    async def get_statistics(self) -> Optional[Dict[str, Any]]:
        """Get statistics from cache."""
        if not self.is_connected():
            return None

        try:
            key = self.PREFIX_STATS + "global"
            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for statistics")
                return json.loads(data)
            logger.debug(f"Cache miss for statistics")
            return None

        except Exception as e:
            logger.error(f"Error getting statistics from cache: {str(e)}")
            return None

    async def set_statistics(self, stats: Dict[str, Any], ttl: int = TTL_STATS) -> bool:
        """Set statistics in cache."""
        if not self.is_connected():
            return False

        try:
            key = self.PREFIX_STATS + "global"
            self.client.setex(key, ttl, json.dumps(stats))
            logger.debug(f"Cached statistics")
            return True

        except Exception as e:
            logger.error(f"Error setting statistics in cache: {str(e)}")
            return False

    # Collections caching

    async def get_collections(
        self,
        limit: int = 50,
        source_name: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get collections from cache."""
        if not self.is_connected():
            return None

        try:
            key = self._generate_cache_key(
                self.PREFIX_COLLECTIONS,
                limit=limit,
                source_name=source_name
            )

            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for collections")
                return json.loads(data)
            logger.debug(f"Cache miss for collections")
            return None

        except Exception as e:
            logger.error(f"Error getting collections from cache: {str(e)}")
            return None

    async def set_collections(
        self,
        collections: List[Dict[str, Any]],
        limit: int = 50,
        source_name: Optional[str] = None,
        ttl: int = TTL_COLLECTIONS
    ) -> bool:
        """Set collections in cache."""
        if not self.is_connected():
            return False

        try:
            key = self._generate_cache_key(
                self.PREFIX_COLLECTIONS,
                limit=limit,
                source_name=source_name
            )

            self.client.setex(key, ttl, json.dumps(collections))
            logger.debug(f"Cached collections")
            return True

        except Exception as e:
            logger.error(f"Error setting collections in cache: {str(e)}")
            return False

    # Sources caching

    async def get_sources(self, active_only: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get sources from cache."""
        if not self.is_connected():
            return None

        try:
            key = self._generate_cache_key(self.PREFIX_SOURCES, active_only=active_only)
            data = self.client.get(key)
            if data:
                logger.debug(f"Cache hit for sources")
                return json.loads(data)
            logger.debug(f"Cache miss for sources")
            return None

        except Exception as e:
            logger.error(f"Error getting sources from cache: {str(e)}")
            return None

    async def set_sources(
        self,
        sources: List[Dict[str, Any]],
        active_only: bool = False,
        ttl: int = TTL_SOURCES
    ) -> bool:
        """Set sources in cache."""
        if not self.is_connected():
            return False

        try:
            key = self._generate_cache_key(self.PREFIX_SOURCES, active_only=active_only)
            self.client.setex(key, ttl, json.dumps(sources))
            logger.debug(f"Cached sources")
            return True

        except Exception as e:
            logger.error(f"Error setting sources in cache: {str(e)}")
            return False

    # Cache invalidation

    async def invalidate_article(self, article_id: str):
        """Invalidate all cache entries related to an article."""
        if not self.is_connected():
            return

        try:
            # Delete specific article
            await self.delete_article(article_id)

            # Invalidate articles lists
            await self.invalidate_pattern(self.PREFIX_ARTICLES + "*")

            # Invalidate search results
            await self.invalidate_pattern(self.PREFIX_SEARCH + "*")

            # Invalidate statistics
            await self.invalidate_pattern(self.PREFIX_STATS + "*")

            logger.info(f"Invalidated cache for article: {article_id}")

        except Exception as e:
            logger.error(f"Error invalidating article cache: {str(e)}")

    async def invalidate_pattern(self, pattern: str):
        """Invalidate all cache entries matching a pattern."""
        if not self.is_connected():
            return

        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} cache entries matching pattern: {pattern}")

        except Exception as e:
            logger.error(f"Error invalidating cache pattern: {str(e)}")

    async def clear_all(self):
        """Clear all cache entries."""
        if not self.is_connected():
            return

        try:
            self.client.flushdb()
            logger.info("Cleared all cache entries")

        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")

    # Cache statistics

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics and information."""
        if not self.is_connected():
            return {}

        try:
            info = self.client.info()
            stats = {
                "connected": True,
                "used_memory_human": info.get("used_memory_human", "0"),
                "total_keys": self.client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": 0.0
            }

            # Calculate hit rate
            total_ops = stats["hits"] + stats["misses"]
            if total_ops > 0:
                stats["hit_rate"] = stats["hits"] / total_ops * 100

            return stats

        except Exception as e:
            logger.error(f"Error getting cache info: {str(e)}")
            return {"connected": False}

    # Decorator for automatic caching

    def cached(self, ttl: int = 300, key_prefix: str = "func:"):
        """
        Decorator for automatic function result caching.

        Usage:
            @cache_service.cached(ttl=600, key_prefix="my_function:")
            async def my_function(arg1, arg2):
                # expensive operation
                return result
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.is_connected():
                    return await func(*args, **kwargs)

                # Generate cache key
                cache_key = self._generate_cache_key(key_prefix, *args, **kwargs)

                # Try to get from cache
                try:
                    cached_data = self.client.get(cache_key)
                    if cached_data:
                        logger.debug(f"Cache hit for function: {func.__name__}")
                        return json.loads(cached_data)
                except Exception as e:
                    logger.error(f"Error reading from cache: {str(e)}")

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                try:
                    self.client.setex(cache_key, ttl, json.dumps(result))
                    logger.debug(f"Cached result for function: {func.__name__}")
                except Exception as e:
                    logger.error(f"Error writing to cache: {str(e)}")

                return result

            return wrapper
        return decorator


# Global cache service instance
cache_service = CacheService()
