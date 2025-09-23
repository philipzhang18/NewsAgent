from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import time
import uuid

from ..models.news_models import NewsArticle, NewsSource, NewsCollection
from ..config.settings import settings

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    """Base class for all news collectors."""
    
    def __init__(self, source: NewsSource):
        self.source = source
        self.collector_id = str(uuid.uuid4())
        self.last_collection = None
        self.is_running = False
        
    @abstractmethod
    async def collect_news(self) -> List[NewsArticle]:
        """Collect news articles from the source."""
        pass
    
    @abstractmethod
    async def validate_source(self) -> bool:
        """Validate if the source is accessible."""
        pass
    
    async def start_collection(self) -> NewsCollection:
        """Start the news collection process."""
        if self.is_running:
            logger.warning(f"Collector {self.collector_id} is already running")
            return None
        
        self.is_running = True
        start_time = time.time()
        
        try:
            logger.info(f"Starting news collection from {self.source.name}")
            
            # Validate source before collection
            if not await self.validate_source():
                raise Exception(f"Source {self.source.name} is not accessible")
            
            # Collect news articles
            articles = await self.collect_news()
            
            # Create collection record
            collection = NewsCollection(
                id=str(uuid.uuid4()),
                source_name=self.source.name,
                collected_at=datetime.utcnow(),
                articles=articles,
                total_articles=len(articles),
                successful_articles=len(articles),
                failed_articles=0,
                processing_time=time.time() - start_time
            )
            
            self.last_collection = collection.collected_at
            logger.info(f"Successfully collected {len(articles)} articles from {self.source.name}")
            
            return collection
            
        except Exception as e:
            logger.error(f"Error collecting news from {self.source.name}: {str(e)}")
            
            # Create failed collection record
            collection = NewsCollection(
                id=str(uuid.uuid4()),
                source_name=self.source.name,
                collected_at=datetime.utcnow(),
                articles=[],
                total_articles=0,
                successful_articles=0,
                failed_articles=1,
                processing_time=time.time() - start_time
            )
            
            return collection
            
        finally:
            self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get collector status information."""
        return {
            "collector_id": self.collector_id,
            "source_name": self.source.name,
            "source_url": self.source.url,
            "is_running": self.is_running,
            "last_collection": self.last_collection.isoformat() if self.last_collection else None,
            "collection_interval": self.source.collection_interval
        }
    
    def should_collect(self) -> bool:
        """Check if it's time to collect news."""
        if not self.last_collection:
            return True
        
        time_since_last = (datetime.utcnow() - self.last_collection).total_seconds()
        return time_since_last >= self.source.collection_interval
    
    def __str__(self):
        return f"{self.__class__.__name__}({self.source.name})"
    
    def __repr__(self):
        return self.__str__()






