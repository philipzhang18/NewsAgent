import asyncio
import feedparser
import logging
from typing import List, Optional
from datetime import datetime
import uuid
from urllib.parse import urlparse

from .base_collector import BaseCollector
from ..models.news_models import NewsArticle, NewsSource
from ..config.settings import settings

logger = logging.getLogger(__name__)

class RSSCollector(BaseCollector):
    """RSS feed news collector."""
    
    def __init__(self, source: NewsSource):
        super().__init__(source)
        self.feed_parser = feedparser
        
    async def validate_source(self) -> bool:
        """Validate RSS feed accessibility."""
        try:
            # Test feed parsing
            feed = self.feed_parser.parse(self.source.url)
            return feed.status == 200 and len(feed.entries) > 0
        except Exception as e:
            logger.error(f"Error validating RSS source {self.source.url}: {str(e)}")
            return False
    
    async def collect_news(self) -> List[NewsArticle]:
        """Collect news from RSS feed."""
        try:
            logger.info(f"Collecting news from RSS feed: {self.source.url}")

            # Parse RSS feed
            feed = self.feed_parser.parse(self.source.url)

            if feed.status != 200:
                raise Exception(f"RSS feed returned status {feed.status}")

            # Extract actual feed title for source name
            feed_title = feed.feed.get('title', self.source.name)
            if feed_title and feed_title != self.source.name:
                logger.info(f"Using feed title as source name: {feed_title}")
                # Temporarily override source name with actual feed title
                original_name = self.source.name
                self.source.name = feed_title

            articles = []
            for entry in feed.entries[:self.source.max_articles]:
                try:
                    article = self._parse_rss_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing RSS entry: {str(e)}")
                    continue

            logger.info(f"Successfully parsed {len(articles)} articles from RSS feed")
            return articles

        except Exception as e:
            logger.error(f"Error collecting from RSS feed {self.source.url}: {str(e)}")
            return []
    
    def _parse_rss_entry(self, entry) -> Optional[NewsArticle]:
        """Parse individual RSS entry into NewsArticle."""
        try:
            # Extract basic information
            title = entry.get('title', '').strip()
            if not title:
                return None
            
            # Extract content
            content = self._extract_content(entry)
            if not content:
                return None
            
            # Extract URL
            url = entry.get('link', '')
            
            # Extract publication date
            published_at = self._parse_date(entry)
            
            # Extract author
            author = entry.get('author', '')
            who = [author] if author else []
            
            # Extract category/tags
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
            elif hasattr(entry, 'category'):
                tags = [entry.category]
            
            # Create NewsArticle
            article = NewsArticle(
                id=str(uuid.uuid4()),
                title=title,
                content=content,
                url=url,
                source_name=self.source.name,
                source_type=self.source.source_type,
                published_at=published_at,
                who=who,
                tags=tags,
                word_count=len(content.split()),
                category=self.source.categories[0] if self.source.categories else None
            )
            
            return article
            
        except Exception as e:
            logger.warning(f"Error parsing RSS entry: {str(e)}")
            return None
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry."""
        # Try different content fields
        content_fields = [
            'content',
            'summary',
            'description',
            'subtitle'
        ]
        
        for field in content_fields:
            if hasattr(entry, field):
                content = getattr(entry, field)
                if isinstance(content, list) and len(content) > 0:
                    content = content[0].value
                elif hasattr(content, 'value'):
                    content = content.value
                
                if content and len(content.strip()) > 10:
                    return content.strip()
        
        return ""
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        date_fields = [
            'published_parsed',
            'updated_parsed',
            'created_parsed'
        ]
        
        for field in date_fields:
            if hasattr(entry, field):
                date_tuple = getattr(entry, field)
                if date_tuple:
                    try:
                        return datetime(*date_tuple[:6])
                    except (ValueError, TypeError):
                        continue
        
        return None
    
    async def get_feed_info(self) -> dict:
        """Get RSS feed metadata information."""
        try:
            feed = self.feed_parser.parse(self.source.url)
            
            return {
                "title": feed.feed.get('title', ''),
                "description": feed.feed.get('description', ''),
                "language": feed.feed.get('language', ''),
                "last_updated": feed.feed.get('updated', ''),
                "entry_count": len(feed.entries),
                "status": feed.status
            }
        except Exception as e:
            logger.error(f"Error getting feed info: {str(e)}")
            return {}






