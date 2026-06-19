"""
Data Collection Service for gathering news from RSS feeds and social media.
"""

import logging
import asyncio
import json
import os
import threading
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..collectors.rss_collector import RSSCollector
from ..collectors.reddit_collector import RedditCollector
from ..collectors.newsapi_collector import NewsAPICollector
from ..collectors.guardian_collector import GuardianCollector
from ..collectors.nytimes_collector import NYTimesCollector
from ..models.news_models import NewsSource, SourceType
from ..config.settings import settings
from .sqlite_storage_service import sqlite_storage
from ..processors.news_processor import NewsProcessor
from .source_diagnostics import build_diagnostic, IMPROVEMENT_HINTS

logger = logging.getLogger(__name__)

# Shared processor for post-collection analysis
_article_processor = NewsProcessor()

# Built-in source names (from env) — delete = deactivate only
_BUILTIN_SOURCE_NAMES = frozenset({
    "NewsAPI", "Reddit News", "The Guardian API", "NYTimes API",
})


class DataCollectionService:
    """Service to collect data from RSS and social media sources."""

    def __init__(self):
        self.sources: List[NewsSource] = []
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sources_config.json')
        self._is_running = False
        self._background_thread: Optional[threading.Thread] = None
        self._last_collection_at: Optional[datetime] = None
        self._last_collection_result: Optional[Dict[str, Any]] = None
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

        # Load API sources from config file
        if config.get("api_sources"):
            for api_config in config["api_sources"]:
                source = NewsSource(
                    name=api_config.get("name", "API Source"),
                    source_type=SourceType.API,
                    url=api_config.get("url", ""),
                    max_articles=api_config.get("max_articles", 50),
                    is_active=api_config.get("is_active", True),
                    categories=api_config.get("categories", ["general"]),
                )
                self.sources.append(source)

        # Load social sources from config file
        if config.get("social_sources"):
            for social_config in config["social_sources"]:
                source = NewsSource(
                    name=social_config.get("name", "Social Source"),
                    source_type=SourceType.SOCIAL_MEDIA,
                    url=social_config.get("url", ""),
                    max_articles=social_config.get("max_articles", 50),
                    is_active=social_config.get("is_active", True),
                    categories=social_config.get("categories", ["news"]),
                )
                self.sources.append(source)

        # Add NewsAPI source if configured (skip duplicate)
        if settings.NEWS_API_KEY and settings.NEWS_API_KEY != "your_newsapi_key_here":
            if not any(s.name == "NewsAPI" for s in self.sources):
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

        # Add Reddit source if configured
        if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
            if not any(s.name == "Reddit News" for s in self.sources):
                reddit_source = NewsSource(
                    name="Reddit News",
                    source_type=SourceType.SOCIAL_MEDIA,
                    url="https://www.reddit.com",
                    max_articles=50,
                    is_active=True,
                    categories=["news", "worldnews", "technology"]
                )
                self.sources.append(reddit_source)

        # Add Guardian API source if configured
        if settings.GUARDIAN_API_KEY and settings.GUARDIAN_API_KEY != "your_guardian_api_key_here":
            if not any(s.name == "The Guardian API" for s in self.sources):
                guardian_source = NewsSource(
                    name="The Guardian API",
                    source_type=SourceType.API,
                    url="https://content.guardianapis.com",
                    max_articles=50,
                    is_active=True,
                    categories=["world", "technology", "science"]
                )
                self.sources.append(guardian_source)

        # Add NYTimes API source if configured
        if settings.NYTIMES_API_KEY and settings.NYTIMES_API_KEY != "your_nytimes_api_key_here":
            if not any(s.name == "NYTimes API" for s in self.sources):
                nytimes_source = NewsSource(
                    name="NYTimes API",
                    source_type=SourceType.API,
                    url="https://api.nytimes.com",
                    max_articles=50,
                    is_active=True,
                    categories=["general"]
                )
                self.sources.append(nytimes_source)

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

    async def collect_from_guardian(self) -> List[Any]:
        """Collect articles from The Guardian API."""
        articles = []

        guardian_sources = [s for s in self.sources if s.source_type == SourceType.API and "Guardian" in s.name]

        if not guardian_sources:
            logger.info("No Guardian sources configured")
            return articles

        logger.info(f"Collecting from {len(guardian_sources)} Guardian sources...")

        for source in guardian_sources:
            try:
                collector = GuardianCollector(source)

                is_valid = await collector.validate_source()
                if not is_valid:
                    logger.warning(f"Guardian source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} articles from {source.name}")
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from Guardian: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_from_nytimes(self) -> List[Any]:
        """Collect articles from NYTimes API."""
        articles = []

        nytimes_sources = [s for s in self.sources if s.source_type == SourceType.API and "NYTimes" in s.name]

        if not nytimes_sources:
            logger.info("No NYTimes sources configured")
            return articles

        logger.info(f"Collecting from {len(nytimes_sources)} NYTimes sources...")

        for source in nytimes_sources:
            try:
                collector = NYTimesCollector(source)

                is_valid = await collector.validate_source()
                if not is_valid:
                    logger.warning(f"NYTimes source validation failed for {source.name}")
                    continue

                source_articles = await collector.collect_news()

                if source_articles:
                    logger.info(f"Collected {len(source_articles)} articles from {source.name}")
                    articles.extend(source_articles)
                else:
                    logger.warning(f"No articles collected from {source.name}")

            except Exception as e:
                logger.error(f"Error collecting from NYTimes: {str(e)}", exc_info=True)
                continue

        return articles

    async def collect_all(self, save_to_db: bool = True) -> Dict[str, Any]:
        """Collect articles from all sources and optionally save to database."""
        logger.info("Starting collection from all sources...")

        collection_start = datetime.now()

        # Collect from all sources in parallel
        rss_task = asyncio.create_task(self.collect_from_rss())
        newsapi_task = asyncio.create_task(self.collect_from_newsapi())
        reddit_task = asyncio.create_task(self.collect_from_reddit())
        guardian_task = asyncio.create_task(self.collect_from_guardian())
        nytimes_task = asyncio.create_task(self.collect_from_nytimes())

        results = await asyncio.gather(
            rss_task, newsapi_task, reddit_task, guardian_task, nytimes_task,
            return_exceptions=True
        )

        rss_articles, newsapi_articles, reddit_articles, guardian_articles, nytimes_articles = results

        # Handle exceptions
        if isinstance(rss_articles, Exception):
            logger.error(f"RSS collection failed: {str(rss_articles)}")
            rss_articles = []

        if isinstance(newsapi_articles, Exception):
            logger.error(f"NewsAPI collection failed: {str(newsapi_articles)}")
            newsapi_articles = []

        if isinstance(reddit_articles, Exception):
            logger.error(f"Reddit collection failed: {str(reddit_articles)}")
            reddit_articles = []

        if isinstance(guardian_articles, Exception):
            logger.error(f"Guardian collection failed: {str(guardian_articles)}")
            guardian_articles = []

        if isinstance(nytimes_articles, Exception):
            logger.error(f"NYTimes collection failed: {str(nytimes_articles)}")
            nytimes_articles = []

        all_articles = []
        if isinstance(rss_articles, list):
            all_articles.extend(rss_articles)
        if isinstance(newsapi_articles, list):
            all_articles.extend(newsapi_articles)
        if isinstance(reddit_articles, list):
            all_articles.extend(reddit_articles)
        if isinstance(guardian_articles, list):
            all_articles.extend(guardian_articles)
        if isinstance(nytimes_articles, list):
            all_articles.extend(nytimes_articles)

        logger.info(f"Total articles collected: {len(all_articles)}")

        diagnostics: List[Dict[str, Any]] = []
        diagnostics.extend(self._diagnose_rss_result(rss_articles))
        diagnostics.extend(self._diagnose_api_result("NewsAPI", newsapi_articles))
        diagnostics.extend(self._diagnose_social_result("Reddit News", reddit_articles))
        diagnostics.extend(self._diagnose_api_result("The Guardian API", guardian_articles))
        diagnostics.extend(self._diagnose_api_result("NYTimes API", nytimes_articles))

        saved_count = 0
        processed_count = 0
        if save_to_db and all_articles:
            if not sqlite_storage.is_connected():
                sqlite_storage.connect()

            saved_count = await sqlite_storage.save_articles(all_articles)
            logger.info(f"Saved {saved_count} raw articles to database")

            batch = all_articles[:settings.MAX_PROCESS_PER_COLLECTION]
            for article in batch:
                try:
                    processed = await _article_processor.process_article(article)
                    if await sqlite_storage.save_article(processed):
                        processed_count += 1
                except Exception as e:
                    logger.error(f"Processing failed for {article.id}: {e}")

            logger.info(f"Processed and updated {processed_count} articles")

        collection_end = datetime.now()
        duration = (collection_end - collection_start).total_seconds()
        self._last_collection_at = collection_end
        self._last_collection_result = {
            "success": True,
            "total_collected": len(all_articles),
            "saved_to_db": saved_count,
            "processed_count": processed_count,
            "duration_seconds": duration,
            "diagnostics": diagnostics,
        }

        return {
            "success": True,
            "total_collected": len(all_articles),
            "rss_articles": len(rss_articles) if isinstance(rss_articles, list) else 0,
            "newsapi_articles": len(newsapi_articles) if isinstance(newsapi_articles, list) else 0,
            "reddit_articles": len(reddit_articles) if isinstance(reddit_articles, list) else 0,
            "guardian_articles": len(guardian_articles) if isinstance(guardian_articles, list) else 0,
            "nytimes_articles": len(nytimes_articles) if isinstance(nytimes_articles, list) else 0,
            "saved_to_db": saved_count,
            "processed_count": processed_count,
            "duration_seconds": duration,
            "timestamp": collection_end.isoformat(),
            "diagnostics": diagnostics,
        }

    def _diagnose_rss_result(self, result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, Exception):
            return [
                build_diagnostic("RSS feeds", "RSS", False, error=str(result), hint_key="network_error")
            ]
        count = len(result) if isinstance(result, list) else 0
        rss_sources = [s for s in self.sources if s.source_type == SourceType.RSS and s.is_active]
        if not rss_sources:
            return [build_diagnostic("RSS", "RSS", False, hint_key="source_disabled")]
        if count == 0:
            return [
                build_diagnostic(s.name, "RSS", False, hint_key="rss_parse_empty")
                for s in rss_sources
            ]
        return [build_diagnostic("RSS feeds", "RSS", True, articles_count=count)]

    def _diagnose_api_result(self, name: str, result: Any) -> List[Dict[str, Any]]:
        source = next((s for s in self.sources if name in s.name), None)
        if not source:
            if name == "NewsAPI" and not settings.NEWS_API_KEY:
                return [build_diagnostic(name, "API", False, hint_key="newsapi_key_missing")]
            if "Guardian" in name and not settings.GUARDIAN_API_KEY:
                return [build_diagnostic(name, "API", False, hint_key="guardian_key_missing")]
            if "NYTimes" in name and not settings.NYTIMES_API_KEY:
                return [build_diagnostic(name, "API", False, hint_key="nytimes_key_missing")]
            return []
        if not source.is_active:
            return [build_diagnostic(name, "API", False, hint_key="source_disabled")]
        if isinstance(result, Exception):
            err = str(result)
            hint = "network_error"
            if "401" in err or "403" in err:
                hint = "newsapi_key_invalid" if "NewsAPI" in name else "api_auth_failed"
            elif "429" in err:
                hint = "api_rate_limit"
            return [build_diagnostic(name, "API", False, error=err, hint_key=hint)]
        count = len(result) if isinstance(result, list) else 0
        if count == 0:
            return [build_diagnostic(name, "API", False, articles_count=0, hint_key="api_no_results")]
        return [build_diagnostic(name, "API", True, articles_count=count)]

    def _diagnose_social_result(self, name: str, result: Any) -> List[Dict[str, Any]]:
        source = next((s for s in self.sources if name in s.name), None)
        if not source:
            if "Reddit" in name and not settings.REDDIT_CLIENT_ID:
                return [build_diagnostic(name, "Social", False, hint_key="reddit_credentials_missing")]
            return []
        if not source.is_active:
            return [build_diagnostic(name, "Social", False, hint_key="source_disabled")]
        if isinstance(result, Exception):
            err = str(result)
            hint = "network_error"
            if "401" in err or "403" in err:
                hint = "reddit_auth_failed"
            elif "429" in err:
                hint = "api_rate_limit"
            return [build_diagnostic(name, "Social", False, error=err, hint_key=hint)]
        count = len(result) if isinstance(result, list) else 0
        if count == 0:
            return [build_diagnostic(name, "Social", False, articles_count=0)]
        return [build_diagnostic(name, "Social", True, articles_count=count)]

    async def test_source_connection(self, source_id: str) -> Dict[str, Any]:
        """Test a single source and return diagnostics."""
        source = self.get_source_by_id(source_id)
        if not source:
            return {"success": False, "error": "Source not found"}

        if not source.is_active:
            return {
                "success": False,
                "message": f"Source {source.name} is inactive",
                "improvement": IMPROVEMENT_HINTS["source_disabled"],
            }

        start = time.time()
        try:
            articles: List[Any] = []
            if source.source_type == SourceType.RSS:
                collector = RSSCollector(source)
                if not await collector.validate_source():
                    return {
                        "success": False,
                        "message": f"RSS validation failed for {source.name}",
                        "improvement": IMPROVEMENT_HINTS["rss_feed_unreachable"],
                    }
                articles = await collector.collect_news()
            elif "NewsAPI" in source.name:
                if not settings.NEWS_API_KEY:
                    return {"success": False, "improvement": IMPROVEMENT_HINTS["newsapi_key_missing"]}
                collector = NewsAPICollector(source)
                if not await collector.validate_source():
                    return {"success": False, "improvement": IMPROVEMENT_HINTS["newsapi_key_invalid"]}
                articles = await collector.collect_news()
            elif "Guardian" in source.name:
                if not settings.GUARDIAN_API_KEY:
                    return {"success": False, "improvement": IMPROVEMENT_HINTS.get("guardian_key_missing", "Configure GUARDIAN_API_KEY in .env")}
                collector = GuardianCollector(source)
                if not await collector.validate_source():
                    return {"success": False, "improvement": "Guardian API key is invalid or expired"}
                articles = await collector.collect_news()
            elif "NYTimes" in source.name:
                if not settings.NYTIMES_API_KEY:
                    return {"success": False, "improvement": IMPROVEMENT_HINTS.get("nytimes_key_missing", "Configure NYTIMES_API_KEY in .env")}
                collector = NYTimesCollector(source)
                if not await collector.validate_source():
                    return {"success": False, "improvement": "NYTimes API key is invalid or expired"}
                articles = await collector.collect_news()
            elif "Reddit" in source.name:
                if not settings.REDDIT_CLIENT_ID:
                    return {"success": False, "improvement": IMPROVEMENT_HINTS["reddit_credentials_missing"]}
                collector = RedditCollector(source)
                if not await collector.validate_source():
                    return {"success": False, "improvement": IMPROVEMENT_HINTS["reddit_auth_failed"]}
                articles = await collector.collect_news()
            else:
                return {"success": False, "error": f"Unsupported source type: {source.source_type}"}

            elapsed_ms = (time.time() - start) * 1000
            count = len(articles) if articles else 0
            return {
                "success": count > 0 or source.source_type == SourceType.RSS,
                "message": f"Collected {count} sample articles from {source.name}",
                "details": {
                    "response_time_ms": round(elapsed_ms, 1),
                    "articles_found": count,
                    "source_type": source.source_type.value,
                },
                "improvement": "" if count > 0 else IMPROVEMENT_HINTS.get("rss_parse_empty", ""),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "improvement": IMPROVEMENT_HINTS["network_error"],
            }

    def add_source(
        self,
        name: str,
        source_type_label: str,
        url: str,
        max_articles: int = 50,
        categories: Optional[List[str]] = None,
    ) -> Optional[NewsSource]:
        """Add a new source and persist to config."""
        type_map = {
            "RSS": SourceType.RSS,
            "API": SourceType.API,
            "Social": SourceType.SOCIAL_MEDIA,
            "social": SourceType.SOCIAL_MEDIA,
            "rss": SourceType.RSS,
            "api": SourceType.API,
        }
        st = type_map.get(source_type_label, SourceType.RSS)
        if any(s.name == name for s in self.sources):
            logger.warning(f"Source {name} already exists")
            return None

        source = NewsSource(
            name=name,
            source_type=st,
            url=url,
            max_articles=max_articles,
            is_active=True,
            categories=categories or ["general"],
        )
        self.sources.append(source)
        self._save_config()
        return source

    def delete_source(self, source_id: str) -> bool:
        """Remove or deactivate a source."""
        source = self.get_source_by_id(source_id)
        if not source:
            return False

        if source.name in _BUILTIN_SOURCE_NAMES:
            source.is_active = False
            self._save_config()
            return True

        self.sources = [s for s in self.sources if self._source_id(s) != source_id]
        self._save_config()
        return True

    async def run_diagnostics(self) -> List[Dict[str, Any]]:
        """Run live collection test for every configured source."""
        results = []
        for source in self.sources:
            sid = self._source_id(source)
            result = await self.test_source_connection(sid)
            result["source_id"] = sid
            result["source_name"] = source.name
            results.append(result)
        return results

    def start_background_collection(self) -> bool:
        """Start periodic background collection in a daemon thread."""
        if self._is_running:
            logger.warning("Background collection is already running")
            return False

        self._is_running = True
        self._background_thread = threading.Thread(
            target=self._background_collection_loop,
            name="news-collection",
            daemon=True,
        )
        self._background_thread.start()
        logger.info("Background collection started")
        return True

    def stop_background_collection(self) -> bool:
        """Stop periodic background collection."""
        if not self._is_running:
            return False
        self._is_running = False
        logger.info("Background collection stopped")
        return True

    def _background_collection_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self._is_running:
                try:
                    loop.run_until_complete(self.collect_all(save_to_db=True))
                except Exception as e:
                    logger.error(f"Background collection error: {e}")
                if not self._is_running:
                    break
                for _ in range(settings.COLLECTION_INTERVAL):
                    if not self._is_running:
                        break
                    time.sleep(1)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def initialize(self):
        """Ensure database is ready for collection."""
        if not sqlite_storage.is_connected():
            sqlite_storage.connect()

    def _source_id(self, source: NewsSource) -> str:
        return source.name.lower().replace(' ', '_').replace('/', '_')

    async def get_collection_status(self) -> Dict[str, Any]:
        """Get status of data collection service."""
        rss_count = len([s for s in self.sources if s.source_type == SourceType.RSS])
        api_count = len([s for s in self.sources if s.source_type == SourceType.API])
        social_count = len([s for s in self.sources if s.source_type == SourceType.SOCIAL_MEDIA])

        db_connected = sqlite_storage.is_connected()
        db_stats: Dict[str, Any] = {}
        articles_by_source: Dict[str, int] = {}
        if db_connected:
            db_stats = await sqlite_storage.get_statistics()
            articles_by_source = db_stats.get("articles_by_source", {})

        collectors: Dict[str, Dict[str, Any]] = {}
        for source in self.sources:
            source_id = self._source_id(source)
            collectors[source_id] = {
                "source_name": source.name,
                "is_running": self._is_running and source.is_active,
                "is_active": source.is_active,
                "last_collection": self._last_collection_at.isoformat() if self._last_collection_at else None,
                "articles_collected": articles_by_source.get(source.name, 0),
            }

        return {
            "service_running": self._is_running,
            "total_collectors": len(self.sources),
            "total_sources": len(self.sources),
            "rss_sources": rss_count,
            "api_sources": api_count,
            "social_sources": social_count,
            "collectors": collectors,
            "database_connected": db_connected,
            "database_stats": db_stats,
            "last_collection": self._last_collection_at.isoformat() if self._last_collection_at else None,
            "last_collection_result": self._last_collection_result,
            "collection_stats": {
                "total_articles": db_stats.get("total_articles", 0),
                "last_collection": self._last_collection_at.isoformat() if self._last_collection_at else None,
            },
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
