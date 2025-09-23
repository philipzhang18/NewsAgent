import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import schedule
import time
import uuid

from ..collectors.base_collector import BaseCollector
from ..collectors.rss_collector import RSSCollector
from ..models.news_models import NewsSource, NewsArticle, NewsCollection
from ..config.settings import settings

logger = logging.getLogger(__name__)

class NewsCollectorService:
    """Main service for coordinating news collection."""
    
    def __init__(self):
        self.collectors: Dict[str, BaseCollector] = {}
        self.collections: List[NewsCollection] = []
        self.is_running = False
        self.collection_stats = {
            "total_collections": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "total_articles": 0,
            "last_collection": None
        }
    
    async def initialize_collectors(self):
        """Initialize news collectors from configuration."""
        try:
            logger.info("Initializing news collectors...")
            
            # Initialize RSS collectors
            for rss_url in settings.RSS_FEEDS:
                if rss_url.strip():
                    source = NewsSource(
                        name=f"RSS_{rss_url.split('/')[-1]}",
                        url=rss_url.strip(),
                        source_type=NewsSource.RSS,
                        collection_interval=settings.COLLECTION_INTERVAL,
                        max_articles=settings.MAX_ARTICLES_PER_SOURCE
                    )
                    
                    collector = RSSCollector(source)
                    self.collectors[collector.collector_id] = collector
                    logger.info(f"Initialized RSS collector: {source.name}")
            
            logger.info(f"Initialized {len(self.collectors)} collectors")
            
        except Exception as e:
            logger.error(f"Error initializing collectors: {str(e)}")
    
    async def start_collection_cycle(self):
        """Start the news collection cycle."""
        if self.is_running:
            logger.warning("News collection service is already running")
            return
        
        self.is_running = True
        logger.info("Starting news collection service...")
        
        try:
            # Schedule collection tasks
            for collector in self.collectors.values():
                schedule.every(collector.source.collection_interval).seconds.do(
                    self._run_collector, collector
                )
            
            # Run initial collection
            await self._run_all_collectors()
            
            # Start scheduled collection loop
            while self.is_running:
                schedule.run_pending()
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in collection cycle: {str(e)}")
        finally:
            self.is_running = False
    
    async def stop_collection_service(self):
        """Stop the news collection service."""
        self.is_running = False
        logger.info("Stopping news collection service...")
    
    async def _run_collector(self, collector: BaseCollector):
        """Run a single collector."""
        try:
            if collector.should_collect():
                collection = await collector.start_collection()
                if collection:
                    self.collections.append(collection)
                    self._update_stats(collection)
                    
                    # Keep only recent collections in memory
                    if len(self.collections) > 100:
                        self.collections = self.collections[-100:]
                        
        except Exception as e:
            logger.error(f"Error running collector {collector.collector_id}: {str(e)}")
    
    async def _run_all_collectors(self):
        """Run all collectors immediately."""
        tasks = []
        for collector in self.collectors.values():
            if collector.should_collect():
                tasks.append(self._run_collector(collector))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _update_stats(self, collection: NewsCollection):
        """Update collection statistics."""
        self.collection_stats["total_collections"] += 1
        
        if collection.successful_articles > 0:
            self.collection_stats["successful_collections"] += 1
        else:
            self.collection_stats["failed_collections"] += 1
        
        self.collection_stats["total_articles"] += collection.total_articles
        self.collection_stats["last_collection"] = collection.collected_at
    
    async def get_collection_status(self) -> Dict[str, Any]:
        """Get the status of all collectors."""
        status = {
            "service_running": self.is_running,
            "total_collectors": len(self.collectors),
            "collection_stats": self.collection_stats,
            "collectors": {}
        }
        
        for collector_id, collector in self.collectors.items():
            status["collectors"][collector_id] = collector.get_status()
        
        return status
    
    async def get_recent_articles(self, limit: int = 50) -> List[NewsArticle]:
        """Get recent articles from all collections."""
        articles = []
        
        for collection in reversed(self.collections):
            articles.extend(collection.articles)
            if len(articles) >= limit:
                break
        
        return articles[:limit]
    
    async def get_articles_by_source(self, source_name: str, limit: int = 50) -> List[NewsArticle]:
        """Get articles from a specific source."""
        articles = []
        
        for collection in reversed(self.collections):
            if collection.source_name == source_name:
                articles.extend(collection.articles)
                if len(articles) >= limit:
                    break
        
        return articles[:limit]
    
    async def get_articles_by_category(self, category: str, limit: int = 50) -> List[NewsArticle]:
        """Get articles by category."""
        articles = []
        
        for collection in reversed(self.collections):
            for article in collection.articles:
                if article.category == category:
                    articles.append(article)
                    if len(articles) >= limit:
                        break
            if len(articles) >= limit:
                break
        
        return articles[:limit]
    
    async def search_articles(self, query: str, limit: int = 50) -> List[NewsArticle]:
        """Search articles by query."""
        articles = []
        query_lower = query.lower()
        
        for collection in reversed(self.collections):
            for article in collection.articles:
                if (query_lower in article.title.lower() or 
                    query_lower in article.content.lower() or
                    any(query_lower in tag.lower() for tag in article.tags)):
                    articles.append(article)
                    if len(articles) >= limit:
                        break
            if len(articles) >= limit:
                break
        
        return articles[:limit]
    
    def get_collector_by_id(self, collector_id: str) -> Optional[BaseCollector]:
        """Get a collector by ID."""
        return self.collectors.get(collector_id)
    
    def get_collector_by_source(self, source_name: str) -> Optional[BaseCollector]:
        """Get a collector by source name."""
        for collector in self.collectors.values():
            if collector.source.name == source_name:
                return collector
        return None






