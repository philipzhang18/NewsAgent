"""
Unified SQLite-backed storage service.
Replaces the previous MongoDB layer with a single local database.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.news_models import NewsArticle, NewsCollection, NewsSource
from .sqlite_storage_service import sqlite_storage

logger = logging.getLogger(__name__)


class StorageService:
    """SQLite persistence layer with NewsArticle-compatible API."""

    def __init__(self):
        self._db = sqlite_storage

    def connect(self) -> bool:
        return self._db.connect()

    def disconnect(self):
        self._db.disconnect()

    def is_connected(self) -> bool:
        return self._db.is_connected()

    def _to_article(self, data: Dict[str, Any]) -> NewsArticle:
        return NewsArticle.from_dict(data)

    async def save_article(self, article: NewsArticle) -> bool:
        if not self.is_connected():
            self.connect()
        return await self._db.save_article(article)

    async def save_articles(self, articles: List[NewsArticle]) -> int:
        if not self.is_connected():
            self.connect()
        return await self._db.save_articles(articles)

    async def get_article(self, article_id: str) -> Optional[NewsArticle]:
        if not self.is_connected():
            self.connect()
        row = await self._db.get_article(article_id)
        return self._to_article(row) if row else None

    async def get_articles(
        self,
        limit: int = 50,
        skip: int = 0,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[NewsArticle]:
        if not self.is_connected():
            self.connect()
        rows = await self._db.get_articles(
            limit=limit,
            skip=skip,
            source_name=source_name,
            category=category,
            sentiment=sentiment,
            start_date=start_date,
            end_date=end_date,
        )
        return [self._to_article(row) for row in rows]

    async def search_articles(self, query: str, limit: int = 50) -> List[NewsArticle]:
        if not self.is_connected():
            self.connect()
        rows = await self._db.search_articles(query, limit=limit)
        return [self._to_article(row) for row in rows]

    async def delete_article(self, article_id: str) -> bool:
        if not self.is_connected():
            return False
        return await self._db.delete_article(article_id)

    async def delete_articles_before(self, cutoff_date: datetime) -> int:
        if not self.is_connected():
            return 0
        return await self._db.delete_articles_before(cutoff_date)

    async def query_articles(self, filters: Dict[str, Any], limit: int = 100) -> List[NewsArticle]:
        if not self.is_connected():
            self.connect()
        rows = await self._db.query_articles(filters, limit=limit)
        return [self._to_article(row) for row in rows]

    async def save_collection(self, collection: NewsCollection) -> bool:
        if collection.articles:
            saved = await self.save_articles(collection.articles)
            return saved > 0
        return True

    async def get_collections(
        self,
        limit: int = 50,
        source_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Collection history is not stored separately; return aggregate stats."""
        stats = await self.get_statistics()
        if not stats:
            return []
        entry = {
            "source_name": source_name or "all",
            "total_articles": stats.get("total_articles", 0),
            "collected_at": stats.get("last_published"),
        }
        return [entry]

    async def save_source(self, source: NewsSource) -> bool:
        logger.debug("Source config persisted via sources_config.json, not SQLite")
        return True

    async def get_sources(self, active_only: bool = False) -> List[Dict[str, Any]]:
        return []

    async def delete_source(self, source_name: str) -> bool:
        return False

    async def get_statistics(self) -> Dict[str, Any]:
        from ..utils.memory_cache import memory_cache
        cached = memory_cache.get("stats:all")
        if cached:
            return cached
        if not self.is_connected():
            self.connect()
        stats = await self._db.get_statistics()
        memory_cache.set("stats:all", stats, ttl=120)
        return stats


storage_service = StorageService()

# Alias for modules that import sqlite_storage directly
sqlite_storage_service = sqlite_storage
