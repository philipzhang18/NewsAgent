"""
New York Times Collector for gathering news from NYTimes Article Search API.
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import requests

from .base_collector import BaseCollector
from ..models.news_models import NewsSource, NewsArticle, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class NYTimesCollector(BaseCollector):
    """Collector for New York Times Article Search API."""

    def __init__(self, source: NewsSource):
        super().__init__(source)
        self.api_key = settings.NYTIMES_API_KEY
        self.base_url = "https://api.nytimes.com/svc/search/v2"

    async def validate_source(self) -> bool:
        """Validate NYTimes API key."""
        if not self.api_key or self.api_key == "your_nytimes_api_key_here":
            logger.error("NYTimes API key not configured")
            return False

        try:
            params = {
                "api-key": self.api_key,
                "q": "news",
                "page": 0
            }
            response = requests.get(
                f"{self.base_url}/articlesearch.json", params=params, timeout=10
            )

            if response.status_code == 200:
                logger.info("NYTimes API access validated successfully")
                return True
            elif response.status_code == 401 or response.status_code == 403:
                logger.error("NYTimes API authentication failed - invalid API key")
                return False
            elif response.status_code == 429:
                logger.warning("NYTimes API rate limit exceeded")
                return False
            else:
                logger.error(f"NYTimes API returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error validating NYTimes API: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """Collect news from NYTimes Article Search API."""
        if not self.api_key:
            logger.warning("NYTimes API key not available")
            return []

        articles = []

        try:
            max_articles = getattr(self.source, 'max_articles', 50)
            query = getattr(self.source, 'query', None) or "news"
            section = getattr(self.source, 'section', None)

            # NYTimes returns 10 articles per page
            pages_needed = min((max_articles + 9) // 10, 5)  # Max 5 pages to avoid rate limit

            # Search within last 7 days
            begin_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

            for page in range(pages_needed):
                params = {
                    "api-key": self.api_key,
                    "q": query,
                    "page": page,
                    "begin_date": begin_date,
                    "sort": "newest"
                }

                if section:
                    params["fq"] = f'section_name:("{section}")'

                logger.info(f"Fetching NYTimes articles page {page + 1} (query={query})")

                response = requests.get(
                    f"{self.base_url}/articlesearch.json", params=params, timeout=15
                )
                response.raise_for_status()

                data = response.json()
                response_data = data.get("response", {})
                docs = response_data.get("docs", [])

                if not docs:
                    break

                for doc in docs:
                    article = self._parse_nytimes_article(doc)
                    if article:
                        articles.append(article)

                if len(articles) >= max_articles:
                    break

            logger.info(f"Collected {len(articles)} articles from NYTimes")
            return articles[:max_articles]

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("NYTimes API rate limit exceeded")
            elif e.response.status_code in (401, 403):
                logger.error("NYTimes API authentication failed")
            else:
                logger.error(f"NYTimes API HTTP error: {str(e)}")
            return articles  # Return what we got so far
        except Exception as e:
            logger.error(f"Error collecting news from NYTimes: {str(e)}")
            return articles

    def _parse_nytimes_article(self, doc: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse a NYTimes API document into a NewsArticle object."""
        try:
            headline = doc.get("headline", {})
            title = headline.get("main", "").strip()
            if not title:
                return None

            web_url = doc.get("web_url", "")
            article_id = f"nytimes_{str(uuid.uuid5(uuid.NAMESPACE_URL, web_url))}"

            # Content fields
            lead_paragraph = doc.get("lead_paragraph", "")
            snippet = doc.get("snippet", "")
            abstract = doc.get("abstract", "")

            content = lead_paragraph or snippet or abstract
            summary = abstract or snippet or lead_paragraph[:300]

            # Parse date
            published_at = None
            pub_date_str = doc.get("pub_date")
            if pub_date_str:
                try:
                    published_at = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Extract author from byline
            byline = doc.get("byline", {})
            author = ""
            if isinstance(byline, dict):
                author = byline.get("original", "")
                if author and author.startswith("By "):
                    author = author[3:]

            # Extract keywords as tags
            tags = []
            for kw in doc.get("keywords", []):
                value = kw.get("value", "")
                if value:
                    tags.append(value)

            section = doc.get("section_name", "general")
            source_name = doc.get("source", "The New York Times")

            article = NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                source_name=source_name,
                collector="NYTimes API",
                url=web_url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                who=[author] if author else [],
                tags=tags[:10],
                category=section.lower() if section else "general"
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing NYTimes article: {str(e)}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get collector status."""
        status = super().get_status()
        status["api_key_configured"] = bool(self.api_key and self.api_key != "your_nytimes_api_key_here")
        return status
