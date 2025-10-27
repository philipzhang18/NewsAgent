"""
Data Collection Service for gathering news from RSS feeds and social media.
"""

import logging
import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..collectors.rss_collector import RSSCollector
from ..collectors.reddit_collector import RedditCollector
from ..collectors.twitter_collector import TwitterCollector
from ..collectors.newsapi_collector import NewsAPICollector
from ..collectors.exa_collector import ExaCollector
from ..models.news_models import NewsSource, SourceType
from ..config.settings import settings
from .sqlite_storage_service import sqlite_storage

logger = logging.getLogger(__name__)


class DataCollectionService:
    """Service to collect data from RSS and social media sources."""

    def __init__(self):
        self.sources: List[NewsSource] = []
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sources_config.json')
        self._initialize_sources()

    def _load_config(self) -> Dict[str, Any]:
        """Load sources configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"Loaded configuration from {self.config_file}")
                    return config
            else:
                logger.info("Configuration file not found, creating default")
                return {"rss_sources": [], "api_sources": [], "social_sources": []}
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return {"rss_sources": [], "api_sources": [], "social_sources": []}

    def _save_config(self):
        """Save current sources configuration to file."""
        try:
            config = {
                "rss_sources": [],
                "api_sources": [],
                "social_sources": []
            }

            for source in self.sources:
                source_dict = {
                    "name": source.name,
                    "url": source.url,
                    "max_articles": source.max_articles,
                    "is_active": source.is_active
                }

                if source.source_type == SourceType.RSS:
                    config["rss_sources"].append(source_dict)
                elif source.source_type == SourceType.API:
                    config["api_sources"].append(source_dict)
                elif source.source_type == SourceType.SOCIAL_MEDIA:
                    config["social_sources"].append(source_dict)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False

    def _initialize_sources(self):
        """Initialize news sources from configuration file or environment."""
        self.sources = []

        # Try to load from configuration file first
        config = self._load_config()

        # Load RSS sources from config file
        if config.get("rss_sources"):
            for rss_config in config["rss_sources"]:
                source = NewsSource(
                    name=rss_config.get("name", "RSS Feed"),
                    source_type=SourceType.RSS,
                    url=rss_config.get("url"),
                    max_articles=rss_config.get("max_articles", 50),
                    is_active=rss_config.get("is_active", True),
                    categories=["general"]
                )
                self.sources.append(source)
                logger.info(f"Loaded RSS source from config: {source.name}")
        else:
            # Fallback to environment-based RSS configuration
            rss_feed_names = {
                "http://feeds.bbci.co.uk/news/rss.xml": "BBC News",
                "https://www.theguardian.com/world/rss": "The Guardian",
                "https://www.aljazeera.com/xml/rss/all.xml": "Al Jazeera",
                "http://rss.cnn.com/rss/edition.rss": "CNN",
                "https://www.reuters.com/rssFeed/worldNews": "Reuters"
            }

            if settings.RSS_FEEDS:
                for idx, feed_url in enumerate(settings.RSS_FEEDS):
                    if feed_url.strip():
                        feed_name = rss_feed_names.get(feed_url.strip())

                        if not feed_name:
                            from urllib.parse import urlparse
                            parsed = urlparse(feed_url)
                            domain = parsed.netloc.replace('www.', '').split('.')[0]
                            feed_name = domain.title() + " RSS"

                        source = NewsSource(
                            name=feed_name,
                            source_type=SourceType.RSS,
                            url=feed_url.strip(),
                            max_articles=50,
                            is_active=True,
                            categories=["general"]
                        )
                        self.sources.append(source)

        # Add NewsAPI source if configured
        if settings.NEWS_API_KEY and settings.NEWS_API_KEY != "your_newsapi_key_here":
            newsapi_source = NewsSource(
                name="NewsAPI",
                source_type=SourceType.API,
                url="https://newsapi.org/v2",
                max_articles=100,
                is_active=True,
                categories=["general"],
                country="us"
            )
            self.sources.append(newsapi_source)

        # Add Twitter source if configured
        if settings.TWITTER_API_KEY or settings.TWITTER_BEARER_TOKEN:
            twitter_source = NewsSource(
                name="Twitter News",
                source_type=SourceType.SOCIAL_MEDIA,
                url="https://twitter.com",
                max_articles=50,
                is_active=True,
                categories=["social_media"]
            )
            self.sources.append(twitter_source)

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

        # Add Exa AI source if configured
        if settings.EXA_API_KEY and settings.EXA_API_KEY != "your_exa_api_key_here":
            exa_source = NewsSource(
                name="Exa AI Search",
                source_type=SourceType.API,
                url="https://api.exa.ai",
                max_articles=50,
                is_active=True,
                categories=["AI", "technology"]
            )
            self.sources.append(exa_source)

        logger.info(f"Initialized {len(self.sources)} news sources")

        # Save initial configuration if file doesn't exist
        if not os.path.exists(self.config_file) and self.sources:
            self._save_config()

    async def collect_from_rss(self) -> List[Any]:
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
                    # NewsArticle objects are returned directly
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from {source.name}: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_from_reddit(self) -> List[Any]:
        """Collect articles from Reddit."""
        articles = []

        reddit_sources = [s for s in self.sources if s.source_type == SourceType.SOCIAL_MEDIA and "Reddit" in s.name]

        if not reddit_sources:
            logger.info("No Reddit sources configured")
            return articles

        logger.info(f"Collecting from {len(reddit_sources)} Reddit sources...")

        for source in reddit_sources:
            try:
                # Update source with subreddits configuration
                source.subreddits = source.categories if source.categories else ["news", "worldnews"]

                collector = RedditCollector(source)

                # Validate source first
                if not await collector.validate_source():
                    logger.warning(f"Reddit source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} posts from {source.name}")
                    # NewsArticle objects are returned directly
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No posts collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from Reddit: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_from_twitter(self) -> List[Any]:
        """Collect articles from Twitter."""
        articles = []

        twitter_sources = [s for s in self.sources if s.source_type == SourceType.SOCIAL_MEDIA and "Twitter" in s.name]

        if not twitter_sources:
            logger.info("No Twitter sources configured")
            return articles

        logger.info(f"Collecting from {len(twitter_sources)} Twitter sources...")

        for source in twitter_sources:
            try:
                # Add default search queries if not configured
                if not hasattr(source, 'search_queries'):
                    source.search_queries = ["breaking news", "top stories", "#news"]

                collector = TwitterCollector(source)

                # Validate source first
                if not await collector.validate_source():
                    logger.warning(f"Twitter source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} tweets from {source.name}")
                    # NewsArticle objects are returned directly
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No tweets collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from Twitter: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_from_newsapi(self) -> List[Any]:
        """Collect articles from NewsAPI."""
        articles = []

        newsapi_sources = [s for s in self.sources if s.source_type == SourceType.API and "NewsAPI" in s.name]

        if not newsapi_sources:
            logger.info("No NewsAPI sources configured")
            return articles

        logger.info(f"Collecting from {len(newsapi_sources)} NewsAPI sources...")

        for source in newsapi_sources:
            try:
                collector = NewsAPICollector(source)

                # Validate source first
                is_valid = await collector.validate_source()
                logger.info(f"NewsAPI validation result: {is_valid}")

                if not is_valid:
                    logger.warning(f"NewsAPI source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} articles from {source.name}")
                    # NewsArticle objects are returned directly
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from NewsAPI: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_from_exa(self) -> List[Any]:
        """Collect articles from Exa AI Search."""
        articles = []

        exa_sources = [s for s in self.sources if s.source_type == SourceType.API and "Exa" in s.name]

        if not exa_sources:
            logger.info("No Exa AI sources configured")
            return articles

        logger.info(f"Collecting from {len(exa_sources)} Exa AI sources...")

        for source in exa_sources:
            try:
                collector = ExaCollector(source)

                # Validate source first
                is_valid = await collector.validate_source()
                logger.info(f"Exa AI validation result: {is_valid}")

                if not is_valid:
                    logger.warning(f"Exa AI source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} articles from {source.name}")
                    # NewsArticle objects are returned directly
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from Exa AI: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_all(self, save_to_db: bool = True) -> Dict[str, Any]:
        """Collect articles from all sources and optionally save to database."""
        logger.info("Starting collection from all sources...")

        collection_start = datetime.now()

        # Collect from RSS, NewsAPI, Twitter, Reddit, and Exa in parallel
        rss_task = asyncio.create_task(self.collect_from_rss())
        newsapi_task = asyncio.create_task(self.collect_from_newsapi())
        twitter_task = asyncio.create_task(self.collect_from_twitter())
        reddit_task = asyncio.create_task(self.collect_from_reddit())
        exa_task = asyncio.create_task(self.collect_from_exa())

        rss_articles, newsapi_articles, twitter_articles, reddit_articles, exa_articles = await asyncio.gather(
            rss_task, newsapi_task, twitter_task, reddit_task, exa_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(rss_articles, Exception):
            logger.error(f"RSS collection failed: {str(rss_articles)}")
            rss_articles = []

        if isinstance(newsapi_articles, Exception):
            logger.error(f"NewsAPI collection failed: {str(newsapi_articles)}")
            newsapi_articles = []

        if isinstance(twitter_articles, Exception):
            logger.error(f"Twitter collection failed: {str(twitter_articles)}")
            twitter_articles = []

        if isinstance(reddit_articles, Exception):
            logger.error(f"Reddit collection failed: {str(reddit_articles)}")
            reddit_articles = []

        if isinstance(exa_articles, Exception):
            logger.error(f"Exa AI collection failed: {str(exa_articles)}")
            exa_articles = []

        all_articles = []
        if isinstance(rss_articles, list):
            all_articles.extend(rss_articles)
        if isinstance(newsapi_articles, list):
            all_articles.extend(newsapi_articles)
        if isinstance(twitter_articles, list):
            all_articles.extend(twitter_articles)
        if isinstance(reddit_articles, list):
            all_articles.extend(reddit_articles)
        if isinstance(exa_articles, list):
            all_articles.extend(exa_articles)

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
            "newsapi_articles": len(newsapi_articles) if isinstance(newsapi_articles, list) else 0,
            "twitter_articles": len(twitter_articles) if isinstance(twitter_articles, list) else 0,
            "reddit_articles": len(reddit_articles) if isinstance(reddit_articles, list) else 0,
            "exa_articles": len(exa_articles) if isinstance(exa_articles, list) else 0,
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

    def update_source(self, source_id: str, name: str = None, url: str = None, status: str = None) -> bool:
        """Update a source configuration and save to file."""
        try:
            # Find source by matching name or URL
            for source in self.sources:
                source_match_id = source.name.lower().replace(' ', '_').replace('/', '_')
                if source_match_id == source_id:
                    if name:
                        logger.info(f"Updating source name from '{source.name}' to '{name}'")
                        source.name = name
                    if url:
                        source.url = url
                    if status:
                        source.is_active = (status == 'active')

                    # Save configuration to file
                    self._save_config()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error updating source: {str(e)}")
            return False

    def get_source_by_id(self, source_id: str) -> Optional[NewsSource]:
        """Get a source by ID."""
        for source in self.sources:
            source_match_id = source.name.lower().replace(' ', '_').replace('/', '_')
            if source_match_id == source_id:
                return source
        return None


# Global instance
data_collection_service = DataCollectionService()
