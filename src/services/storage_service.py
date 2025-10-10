"""
Storage service for persisting news articles and collections to MongoDB.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient, DESCENDING, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import time

from ..models.news_models import NewsArticle, NewsCollection, NewsSource
from ..config.settings import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing data persistence with MongoDB."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.articles_collection = None
        self.collections_collection = None
        self.sources_collection = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}")
            self.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )

            # Test connection
            self.client.admin.command('ping')

            # Get database
            db_name = settings.MONGODB_URI.split('/')[-1] or 'news_agent'
            self.db = self.client[db_name]

            # Get collections
            self.articles_collection = self.db['articles']
            self.collections_collection = self.db['collections']
            self.sources_collection = self.db['sources']

            # Create indexes
            self._create_indexes()

            self._connected = True
            logger.info("Successfully connected to MongoDB")
            return True

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            self._connected = False
            return False

    def _create_indexes(self):
        """Create database indexes for better performance."""
        try:
            # Articles indexes
            self.articles_collection.create_index([("id", ASCENDING)], unique=True)
            self.articles_collection.create_index([("source_name", ASCENDING)])
            self.articles_collection.create_index([("published_at", DESCENDING)])
            self.articles_collection.create_index([("collected_at", DESCENDING)])
            self.articles_collection.create_index([("category", ASCENDING)])
            self.articles_collection.create_index([("sentiment", ASCENDING)])

            # Collections indexes
            self.collections_collection.create_index([("id", ASCENDING)], unique=True)
            self.collections_collection.create_index([("source_name", ASCENDING)])
            self.collections_collection.create_index([("collected_at", DESCENDING)])

            # Sources indexes
            self.sources_collection.create_index([("name", ASCENDING)], unique=True)
            self.sources_collection.create_index([("source_type", ASCENDING)])

            logger.info("Database indexes created successfully")

        except Exception as e:
            logger.warning(f"Error creating indexes: {str(e)}")

    def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")

    def is_connected(self) -> bool:
        """Check if connected to MongoDB."""
        return self._connected

    # Article operations

    async def save_article(self, article: NewsArticle) -> bool:
        """Save a single article to database."""
        if not self.is_connected():
            logger.warning("Not connected to MongoDB")
            return False

        try:
            article_dict = article.to_dict()
            self.articles_collection.update_one(
                {"id": article.id},
                {"$set": article_dict},
                upsert=True
            )
            logger.debug(f"Saved article: {article.id}")
            return True

        except Exception as e:
            logger.error(f"Error saving article {article.id}: {str(e)}")
            return False

    async def save_articles(self, articles: List[NewsArticle]) -> int:
        """Save multiple articles to database."""
        if not self.is_connected():
            logger.warning("Not connected to MongoDB")
            return 0

        saved_count = 0
        for article in articles:
            if await self.save_article(article):
                saved_count += 1

        logger.info(f"Saved {saved_count}/{len(articles)} articles")
        return saved_count

    async def get_article(self, article_id: str) -> Optional[NewsArticle]:
        """Get a single article by ID."""
        if not self.is_connected():
            return None

        try:
            article_dict = self.articles_collection.find_one({"id": article_id})
            if article_dict:
                article_dict.pop('_id', None)  # Remove MongoDB _id
                return NewsArticle.from_dict(article_dict)
            return None

        except Exception as e:
            logger.error(f"Error getting article {article_id}: {str(e)}")
            return None

    async def get_articles(
        self,
        limit: int = 50,
        skip: int = 0,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[NewsArticle]:
        """Get articles with optional filtering."""
        if not self.is_connected():
            return []

        try:
            # Build query
            query = {}
            if source_name:
                query["source_name"] = source_name
            if category:
                query["category"] = category
            if sentiment:
                query["sentiment"] = sentiment
            if start_date or end_date:
                date_query = {}
                if start_date:
                    date_query["$gte"] = start_date.isoformat()
                if end_date:
                    date_query["$lte"] = end_date.isoformat()
                query["published_at"] = date_query

            # Execute query
            cursor = self.articles_collection.find(query).sort(
                "published_at", DESCENDING
            ).skip(skip).limit(limit)

            articles = []
            for doc in cursor:
                doc.pop('_id', None)
                articles.append(NewsArticle.from_dict(doc))

            return articles

        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return []

    async def search_articles(self, query: str, limit: int = 50) -> List[NewsArticle]:
        """Search articles by text query."""
        if not self.is_connected():
            return []

        try:
            # Use text search or regex
            search_query = {
                "$or": [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"content": {"$regex": query, "$options": "i"}},
                    {"tags": {"$regex": query, "$options": "i"}}
                ]
            }

            cursor = self.articles_collection.find(search_query).sort(
                "published_at", DESCENDING
            ).limit(limit)

            articles = []
            for doc in cursor:
                doc.pop('_id', None)
                articles.append(NewsArticle.from_dict(doc))

            return articles

        except Exception as e:
            logger.error(f"Error searching articles: {str(e)}")
            return []

    async def delete_article(self, article_id: str) -> bool:
        """Delete an article by ID."""
        if not self.is_connected():
            return False

        try:
            result = self.articles_collection.delete_one({"id": article_id})
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"Error deleting article {article_id}: {str(e)}")
            return False

    # Collection operations

    async def save_collection(self, collection: NewsCollection) -> bool:
        """Save a collection to database."""
        if not self.is_connected():
            return False

        try:
            collection_dict = collection.to_dict()
            self.collections_collection.update_one(
                {"id": collection.id},
                {"$set": collection_dict},
                upsert=True
            )

            # Also save articles
            await self.save_articles(collection.articles)

            logger.info(f"Saved collection: {collection.id}")
            return True

        except Exception as e:
            logger.error(f"Error saving collection {collection.id}: {str(e)}")
            return False

    async def get_collections(
        self,
        limit: int = 50,
        source_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get collections with optional filtering."""
        if not self.is_connected():
            return []

        try:
            query = {}
            if source_name:
                query["source_name"] = source_name

            cursor = self.collections_collection.find(query).sort(
                "collected_at", DESCENDING
            ).limit(limit)

            collections = []
            for doc in cursor:
                doc.pop('_id', None)
                # Don't include full articles in collection list
                doc.pop('articles', None)
                collections.append(doc)

            return collections

        except Exception as e:
            logger.error(f"Error getting collections: {str(e)}")
            return []

    # Source operations

    async def save_source(self, source: NewsSource) -> bool:
        """Save a news source to database."""
        if not self.is_connected():
            return False

        try:
            source_dict = source.to_dict()
            self.sources_collection.update_one(
                {"name": source.name},
                {"$set": source_dict},
                upsert=True
            )
            logger.info(f"Saved source: {source.name}")
            return True

        except Exception as e:
            logger.error(f"Error saving source {source.name}: {str(e)}")
            return False

    async def get_sources(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get all news sources."""
        if not self.is_connected():
            return []

        try:
            query = {}
            if active_only:
                query["is_active"] = True

            cursor = self.sources_collection.find(query)

            sources = []
            for doc in cursor:
                doc.pop('_id', None)
                sources.append(doc)

            return sources

        except Exception as e:
            logger.error(f"Error getting sources: {str(e)}")
            return []

    async def delete_source(self, source_name: str) -> bool:
        """Delete a news source."""
        if not self.is_connected():
            return False

        try:
            result = self.sources_collection.delete_one({"name": source_name})
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"Error deleting source {source_name}: {str(e)}")
            return False

    # Statistics

    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self.is_connected():
            return {}

        try:
            stats = {
                "total_articles": self.articles_collection.count_documents({}),
                "total_collections": self.collections_collection.count_documents({}),
                "total_sources": self.sources_collection.count_documents({}),
                "active_sources": self.sources_collection.count_documents({"is_active": True}),
                "articles_by_sentiment": {},
                "articles_by_source": {}
            }

            # Sentiment distribution
            pipeline = [
                {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
            ]
            for doc in self.articles_collection.aggregate(pipeline):
                if doc['_id']:
                    stats["articles_by_sentiment"][doc['_id']] = doc['count']

            # Source distribution
            pipeline = [
                {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            for doc in self.articles_collection.aggregate(pipeline):
                if doc['_id']:
                    stats["articles_by_source"][doc['_id']] = doc['count']

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}


# Global storage service instance
storage_service = StorageService()
