"""
Data Collection Service for gathering news from RSS feeds and social media.
"""

import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from ..collectors.rss_collector import RSSCollector
from ..collectors.reddit_collector import RedditCollector
from ..models.news_models import NewsSource, SourceType
from ..config.settings import settings
from .sqlite_storage_service import sqlite_storage

logger = logging.getLogger(__name__)


class DataCollectionService:
    """Service to collect data from RSS and social media sources."""

    def __init__(self):
        self.sources: List[NewsSource] = []
        self._initialize_sources()

    def _initialize_sources(self):
        """Initialize news sources from configuration."""
        self.sources = []

        # Add RSS feeds from configuration
        if settings.RSS_FEEDS:
            for idx, feed_url in enumerate(settings.RSS_FEEDS):
                if feed_url.strip():
                    source = NewsSource(
                        name=f"RSS Feed {idx + 1}",
                        source_type=SourceType.RSS,
                        url=feed_url.strip(),
                        max_articles=50,
                        is_active=True,
                        categories=["general"]
                    )
                    self.sources.append(source)

        # Add Reddit source if configured
        if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
            reddit_source = NewsSource(
                name="Reddit News",
                source_type=SourceType.SOCIAL_MEDIA,
                url="https://www.reddit.com",
                max_articles=50,
                is_active=True,
                categories=["news", "worldnews", "technology"]
            )
            self.sources.append(reddit_source)

        logger.info(f"Initialized {len(self.sources)} news sources")

    async def collect_from_rss(self) -> List[Dict[str, Any]]:
        """Collect articles from all RSS feeds."""
        articles = []

        rss_sources = [s for s in self.sources if s.source_type == SourceType.RSS]

        logger.info(f"Collecting from {len(rss_sources)} RSS feeds...")

        for source in rss_sources:
            try:
                collector = RSSCollector(source)
                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} articles from {source.name}")
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from {source.name}: {str(e)}")
                continue

        return articles

    async def collect_from_reddit(self) -> List[Dict[str, Any]]:
        """Collect articles from Reddit."""
        articles = []

        reddit_sources = [s for s in self.sources if s.source_type == SourceType.SOCIAL_MEDIA]

        if not reddit_sources:
            logger.info("No Reddit sources configured")
            return articles

        logger.info(f"Collecting from {len(reddit_sources)} Reddit sources...")

        for source in reddit_sources:
            try:
                collector = RedditCollector(source)

                # Validate source first
                if not await collector.validate_source():
                    logger.warning(f"Reddit source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} posts from {source.name}")
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No posts collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from Reddit: {str(e)}")
                continue

        return articles

    async def collect_all(self, save_to_db: bool = True) -> Dict[str, Any]:
        """Collect articles from all sources and optionally save to database."""
        logger.info("Starting collection from all sources...")

        collection_start = datetime.now()

        # Collect from RSS and Reddit in parallel
        rss_task = asyncio.create_task(self.collect_from_rss())
        reddit_task = asyncio.create_task(self.collect_from_reddit())

        rss_articles, reddit_articles = await asyncio.gather(rss_task, reddit_task, return_exceptions=True)

        # Handle exceptions
        if isinstance(rss_articles, Exception):
            logger.error(f"RSS collection failed: {str(rss_articles)}")
            rss_articles = []

        if isinstance(reddit_articles, Exception):
            logger.error(f"Reddit collection failed: {str(reddit_articles)}")
            reddit_articles = []

        all_articles = []
        if isinstance(rss_articles, list):
            all_articles.extend(rss_articles)
        if isinstance(reddit_articles, list):
            all_articles.extend(reddit_articles)

        logger.info(f"Total articles collected: {len(all_articles)}")

        # Save to database
        saved_count = 0
        if save_to_db and all_articles:
            if not sqlite_storage.is_connected():
                sqlite_storage.connect()

            saved_count = await sqlite_storage.save_articles(all_articles)
            logger.info(f"Saved {saved_count} articles to database")

        collection_end = datetime.now()
        duration = (collection_end - collection_start).total_seconds()

        return {
            "success": True,
            "total_collected": len(all_articles),
            "rss_articles": len(rss_articles) if isinstance(rss_articles, list) else 0,
            "reddit_articles": len(reddit_articles) if isinstance(reddit_articles, list) else 0,
            "saved_to_db": saved_count,
            "duration_seconds": duration,
            "timestamp": collection_end.isoformat()
        }

    async def get_collection_status(self) -> Dict[str, Any]:
        """Get status of data collection service."""
        rss_count = len([s for s in self.sources if s.source_type == SourceType.RSS])
        social_count = len([s for s in self.sources if s.source_type == SourceType.SOCIAL_MEDIA])

        db_connected = sqlite_storage.is_connected()

        # Get database stats if connected
        db_stats = {}
        if db_connected:
            db_stats = await sqlite_storage.get_statistics()

        return {
            "service_running": True,
            "total_sources": len(self.sources),
            "rss_sources": rss_count,
            "social_sources": social_count,
            "database_connected": db_connected,
            "database_stats": db_stats
        }


# Global instance
data_collection_service = DataCollectionService()
