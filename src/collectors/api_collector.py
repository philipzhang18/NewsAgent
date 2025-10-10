"""
API-based news collector for NewsAPI and similar services.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import requests

from .base_collector import BaseCollector
from ..models.news_models import NewsArticle, NewsSource, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class APICollector(BaseCollector):
    """News API collector for NewsAPI.org and similar services."""

    def __init__(self, source: NewsSource, api_key: Optional[str] = None):
        super().__init__(source)
        self.api_key = api_key or settings.NEWS_API_KEY
        self.base_url = "https://newsapi.org/v2"
        self.session = requests.Session()

    async def validate_source(self) -> bool:
        """Validate API accessibility."""
        try:
            # Test API with a simple request
            params = {
                "apiKey": self.api_key,
                "pageSize": 1
            }

            response = self.session.get(
                f"{self.base_url}/top-headlines",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return False
            else:
                logger.error(f"API returned status code {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error validating API source {self.source.url}: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """Collect news from NewsAPI."""
        try:
            logger.info(f"Collecting news from NewsAPI: {self.source.name}")

            # Determine endpoint based on source configuration
            if hasattr(self.source, 'query') and self.source.query:
                articles = await self._collect_everything()
            else:
                articles = await self._collect_top_headlines()

            logger.info(f"Successfully collected {len(articles)} articles from NewsAPI")
            return articles

        except Exception as e:
            logger.error(f"Error collecting from NewsAPI {self.source.url}: {str(e)}")
            return []

    async def _collect_top_headlines(self) -> List[NewsArticle]:
        """Collect top headlines."""
        try:
            params = {
                "apiKey": self.api_key,
                "pageSize": min(self.source.max_articles, 100)
            }

            # Add optional parameters
            if hasattr(self.source, 'country') and self.source.country:
                params["country"] = self.source.country
            else:
                params["country"] = "us"

            if self.source.categories and len(self.source.categories) > 0:
                # NewsAPI supports single category
                params["category"] = self.source.categories[0]

            if self.source.language:
                params["language"] = self.source.language

            response = self.session.get(
                f"{self.base_url}/top-headlines",
                params=params,
                timeout=settings.REQUEST_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"API returned error: {data.get('message', 'Unknown error')}")

            articles = []
            for item in data.get("articles", []):
                article = self._parse_api_article(item)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            logger.error(f"Error collecting top headlines: {str(e)}")
            return []

    async def _collect_everything(self) -> List[NewsArticle]:
        """Collect using /everything endpoint with query."""
        try:
            query = getattr(self.source, 'query', '')
            if not query:
                logger.warning("No query specified for everything endpoint")
                return []

            params = {
                "apiKey": self.api_key,
                "q": query,
                "pageSize": min(self.source.max_articles, 100),
                "sortBy": "publishedAt",
                "language": self.source.language or "en"
            }

            response = self.session.get(
                f"{self.base_url}/everything",
                params=params,
                timeout=settings.REQUEST_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"API returned error: {data.get('message', 'Unknown error')}")

            articles = []
            for item in data.get("articles", []):
                article = self._parse_api_article(item)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            logger.error(f"Error collecting with query: {str(e)}")
            return []

    def _parse_api_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse NewsAPI article into NewsArticle."""
        try:
            # Extract basic information
            title = item.get('title', '').strip()
            if not title or title == "[Removed]":
                return None

            # Extract content
            content = item.get('content', '') or item.get('description', '')
            if not content or content == "[Removed]":
                content = item.get('description', '')

            if not content:
                return None

            # Clean content (NewsAPI truncates at [+XXX chars])
            if '[+' in content and 'chars]' in content:
                content = content.split('[+')[0].strip()

            # Extract URL
            url = item.get('url', '')

            # Extract publication date
            published_at = self._parse_date(item.get('publishedAt'))

            # Extract source
            source_info = item.get('source', {})
            source_name = source_info.get('name', self.source.name)

            # Extract author
            author = item.get('author', '')
            who = [author] if author and author != "None" else []

            # Extract image
            image_url = item.get('urlToImage', '')
            image_urls = [image_url] if image_url else []

            # Create NewsArticle
            article = NewsArticle(
                id=str(uuid.uuid4()),
                title=title,
                content=content,
                summary=item.get('description', ''),
                url=url,
                source_name=source_name,
                source_type=self.source.source_type,
                published_at=published_at,
                who=who,
                word_count=len(content.split()),
                image_urls=image_urls,
                category=self.source.categories[0] if self.source.categories else None
            )

            return article

        except Exception as e:
            logger.warning(f"Error parsing API article: {str(e)}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None

        try:
            # NewsAPI returns ISO 8601 format
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Error parsing date {date_str}: {str(e)}")
            return None

    async def get_sources_list(self) -> List[Dict[str, Any]]:
        """Get list of available sources from NewsAPI."""
        try:
            params = {
                "apiKey": self.api_key
            }

            if self.source.language:
                params["language"] = self.source.language

            if hasattr(self.source, 'country') and self.source.country:
                params["country"] = self.source.country

            if self.source.categories:
                params["category"] = self.source.categories[0]

            response = self.session.get(
                f"{self.base_url}/sources",
                params=params,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return data.get("sources", [])

            return []

        except Exception as e:
            logger.error(f"Error getting sources list: {str(e)}")
            return []

    def __del__(self):
        """Cleanup session on deletion."""
        if hasattr(self, 'session'):
            self.session.close()
