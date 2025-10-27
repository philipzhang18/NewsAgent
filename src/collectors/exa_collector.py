"""
Exa Search Collector for gathering AI-related news using Exa AI search.
Exa is a powerful search engine optimized for AI applications.
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


class ExaCollector(BaseCollector):
    """Collector for Exa AI search engine."""

    def __init__(self, source: NewsSource):
        """
        Initialize Exa collector.

        Args:
            source: NewsSource configuration for Exa
        """
        super().__init__(source)
        self.api_key = settings.EXA_API_KEY
        self.base_url = "https://api.exa.ai"

    async def validate_source(self) -> bool:
        """Validate Exa configuration and API key."""
        if not self.api_key or self.api_key == "your_exa_api_key_here":
            logger.error("Exa API key not configured")
            return False

        try:
            # Test API key with a simple search
            url = f"{self.base_url}/search"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
            payload = {
                "query": "AI news",
                "num_results": 1,
                "type": "neural"
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                logger.info("Exa API access validated successfully")
                return True
            elif response.status_code == 401:
                logger.error("Exa API authentication failed - invalid API key")
                return False
            elif response.status_code == 429:
                logger.warning("Exa API rate limit exceeded")
                return False
            else:
                logger.error(f"Exa API returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error validating Exa API: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """
        Collect AI news using Exa search.

        Returns:
            List of NewsArticle objects
        """
        if not self.api_key:
            logger.warning("Exa API key not available")
            return []

        articles = []

        try:
            # Get configuration from source
            max_articles = getattr(self.source, 'max_articles', 50)
            query = getattr(self.source, 'query', 'artificial intelligence OR machine learning OR AI news OR GPT OR LLM')

            # Search with Exa
            logger.info(f"Searching Exa for: {query}")
            search_results = await self._search_exa(
                query=query,
                num_results=max_articles
            )

            articles.extend(search_results)
            logger.info(f"Collected {len(articles)} articles from Exa")
            return articles

        except Exception as e:
            logger.error(f"Error collecting news from Exa: {str(e)}")
            return []

    async def _search_exa(
        self,
        query: str,
        num_results: int = 50
    ) -> List[NewsArticle]:
        """
        Search for content using Exa AI.

        Args:
            query: Search query string
            num_results: Maximum number of results

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            url = f"{self.base_url}/search"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }

            # Search within last 7 days for fresh content
            start_published_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            payload = {
                "query": query,
                "num_results": min(num_results, 100),  # Exa max is 100
                "type": "neural",  # Use neural search for better AI understanding
                "use_autoprompt": True,  # Let Exa optimize the query
                "start_published_date": start_published_date,
                "contents": {
                    "text": {
                        "max_characters": 2000
                    }
                }
            }

            logger.info(f"Exa search: {query} (max {num_results} results)")

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get("results"):
                results = data["results"]
                logger.info(f"Exa returned {len(results)} results")

                for result_data in results:
                    article = self._parse_exa_result(result_data)
                    if article:
                        articles.append(article)

            return articles

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Exa API rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("Exa API authentication failed")
            else:
                logger.error(f"Exa API HTTP error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error searching Exa: {str(e)}")
            return []

    def _parse_exa_result(self, result_data: Dict[str, Any]) -> Optional[NewsArticle]:
        """
        Parse an Exa search result into a NewsArticle object.

        Args:
            result_data: Result data from Exa

        Returns:
            NewsArticle object or None
        """
        try:
            # Extract basic information
            title = result_data.get("title", "").strip()
            if not title:
                return None

            # Generate unique ID
            url = result_data.get("url", "")
            article_id = f"exa_{str(uuid.uuid5(uuid.NAMESPACE_URL, url))}"

            # Extract content
            text_data = result_data.get("text", "")
            summary = result_data.get("summary", "")

            # Use text as content
            content = text_data if text_data else summary

            # Use first 200 chars as summary if not provided
            if not summary and content:
                summary = content[:200] + "..." if len(content) > 200 else content

            # Extract author/source
            author = result_data.get("author", "")

            # Parse publication date
            published_at_str = result_data.get("published_date")
            published_at = None
            if published_at_str:
                try:
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                except:
                    pass

            # Extract score as confidence metric
            score = result_data.get("score", 0)

            # Create article
            article = NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                source_name="Exa AI Search",
                collector="Exa AI",
                url=url,
                published_at=published_at or datetime.now(timezone.utc),
                collected_at=datetime.now(timezone.utc),
                who=[author] if author else [],
                category="AI"
            )

            # Store Exa score in metadata if available
            if hasattr(article, 'metadata'):
                article.metadata = {"exa_score": score}

            return article

        except Exception as e:
            logger.error(f"Error parsing Exa result: {str(e)}")
            return None

    def get_collector_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        stats = super().get_collector_stats()

        stats.update({
            "api_key_configured": bool(self.api_key and self.api_key != "your_exa_api_key_here"),
            "base_url": self.base_url,
            "search_type": "neural"
        })

        return stats
