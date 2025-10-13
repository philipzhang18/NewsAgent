"""
NewsAPI Collector for gathering news from NewsAPI.org.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import requests

from .base_collector import BaseCollector
from ..models.news_models import NewsSource, NewsArticle, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class NewsAPICollector(BaseCollector):
    """Collector for NewsAPI.org news service."""

    def __init__(self, source: NewsSource):
        """
        Initialize NewsAPI collector.

        Args:
            source: NewsSource configuration for NewsAPI
        """
        super().__init__(source)
        self.api_key = settings.NEWS_API_KEY
        self.base_url = "https://newsapi.org/v2"

    async def validate_source(self) -> bool:
        """Validate NewsAPI configuration and API key."""
        if not self.api_key or self.api_key == "your_newsapi_key_here":
            logger.error("NewsAPI key not configured")
            return False

        try:
            # Test API key with a simple request
            url = f"{self.base_url}/top-headlines"
            params = {
                "apiKey": self.api_key,
                "country": "us",
                "pageSize": 1
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                logger.info("NewsAPI access validated successfully")
                return True
            elif response.status_code == 401:
                logger.error("NewsAPI authentication failed - invalid API key")
                return False
            elif response.status_code == 429:
                logger.warning("NewsAPI rate limit exceeded")
                return False
            else:
                logger.error(f"NewsAPI returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error validating NewsAPI: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """
        Collect news from NewsAPI.

        Returns:
            List of NewsArticle objects
        """
        if not self.api_key:
            logger.warning("NewsAPI key not available")
            return []

        articles = []

        try:
            # Get configuration from source
            max_articles = getattr(self.source, 'max_articles', 100)
            country = getattr(self.source, 'country', 'us')
            category = getattr(self.source, 'category', None)
            query = getattr(self.source, 'query', None)

            if query:
                # Use 'everything' endpoint for search queries
                collected_articles = await self._collect_everything(
                    query=query,
                    max_articles=max_articles
                )
            else:
                # Use 'top-headlines' endpoint
                collected_articles = await self._collect_top_headlines(
                    country=country,
                    category=category,
                    max_articles=max_articles
                )

            articles.extend(collected_articles)
            logger.info(f"Collected {len(articles)} articles from NewsAPI")
            return articles

        except Exception as e:
            logger.error(f"Error collecting news from NewsAPI: {str(e)}")
            return []

    async def _collect_top_headlines(
        self,
        country: str = "us",
        category: Optional[str] = None,
        max_articles: int = 100
    ) -> List[NewsArticle]:
        """
        Collect top headlines from NewsAPI.

        Args:
            country: Country code (us, gb, etc.)
            category: Category filter (business, technology, etc.)
            max_articles: Maximum number of articles

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            url = f"{self.base_url}/top-headlines"
            params = {
                "apiKey": self.api_key,
                "country": country,
                "pageSize": min(max_articles, 100)  # NewsAPI max is 100
            }

            if category:
                params["category"] = category

            logger.info(f"Fetching top headlines from NewsAPI (country={country}, category={category})")

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "ok":
                newsapi_articles = data.get("articles", [])
                logger.info(f"NewsAPI returned {len(newsapi_articles)} articles")

                for article_data in newsapi_articles:
                    article = self._parse_newsapi_article(article_data)
                    if article:
                        articles.append(article)

            return articles

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("NewsAPI rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("NewsAPI authentication failed")
            else:
                logger.error(f"NewsAPI HTTP error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error collecting top headlines: {str(e)}")
            return []

    async def _collect_everything(
        self,
        query: str,
        max_articles: int = 100
    ) -> List[NewsArticle]:
        """
        Search all articles from NewsAPI.

        Args:
            query: Search query
            max_articles: Maximum number of articles

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            url = f"{self.base_url}/everything"

            # Search within last 7 days
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            params = {
                "apiKey": self.api_key,
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": min(max_articles, 100),
                "from": from_date
            }

            logger.info(f"Searching NewsAPI for: {query}")

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "ok":
                newsapi_articles = data.get("articles", [])
                logger.info(f"NewsAPI search returned {len(newsapi_articles)} articles")

                for article_data in newsapi_articles:
                    article = self._parse_newsapi_article(article_data)
                    if article:
                        articles.append(article)

            return articles

        except Exception as e:
            logger.error(f"Error searching NewsAPI: {str(e)}")
            return []

    def _parse_newsapi_article(self, article_data: Dict[str, Any]) -> Optional[NewsArticle]:
        """
        Parse a NewsAPI article into a NewsArticle object.

        Args:
            article_data: Article data from NewsAPI

        Returns:
            NewsArticle object or None
        """
        try:
            # Extract basic information
            title = article_data.get("title", "").strip()
            if not title or title == "[Removed]":
                return None

            # Generate unique ID
            url = article_data.get("url", "")
            article_id = f"newsapi_{str(uuid.uuid5(uuid.NAMESPACE_URL, url))}"

            # Extract content
            description = article_data.get("description", "")
            content = article_data.get("content", "")

            # Use description as summary
            summary = description if description else (content[:200] if content else "")

            # Full content
            full_content = content if content else description

            # Extract source
            source_data = article_data.get("source", {})
            source_name = source_data.get("name", "NewsAPI")

            # Parse publication date
            published_at_str = article_data.get("publishedAt")
            published_at = None
            if published_at_str:
                try:
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                except:
                    pass

            # Extract author
            author = article_data.get("author", "")

            # Create article
            article = NewsArticle(
                id=article_id,
                title=title,
                content=full_content,
                summary=summary,
                source_name=source_name,
                url=url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                who=[author] if author else [],
                category="general"
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing NewsAPI article: {str(e)}")
            return None

    def get_collector_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        stats = super().get_collector_stats()

        stats.update({
            "api_key_configured": bool(self.api_key and self.api_key != "your_newsapi_key_here"),
            "base_url": self.base_url
        })

        return stats
