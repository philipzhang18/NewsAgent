"""
Guardian Collector for gathering news from The Guardian Open Platform API.
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


class GuardianCollector(BaseCollector):
    """Collector for The Guardian Open Platform API."""

    def __init__(self, source: NewsSource):
        super().__init__(source)
        self.api_key = settings.GUARDIAN_API_KEY
        self.base_url = "https://content.guardianapis.com"

    async def validate_source(self) -> bool:
        """Validate Guardian API key."""
        if not self.api_key or self.api_key == "your_guardian_api_key_here":
            logger.error("Guardian API key not configured")
            return False

        try:
            params = {
                "api-key": self.api_key,
                "page-size": 1
            }
            response = requests.get(
                f"{self.base_url}/search", params=params, timeout=10
            )

            if response.status_code == 200:
                logger.info("Guardian API access validated successfully")
                return True
            elif response.status_code == 401 or response.status_code == 403:
                logger.error("Guardian API authentication failed - invalid API key")
                return False
            else:
                logger.error(f"Guardian API returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error validating Guardian API: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """Collect news from The Guardian API."""
        if not self.api_key:
            logger.warning("Guardian API key not available")
            return []

        articles = []

        try:
            max_articles = getattr(self.source, 'max_articles', 50)
            query = getattr(self.source, 'query', None)
            section = getattr(self.source, 'section', None)

            # Search within last 7 days
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            params = {
                "api-key": self.api_key,
                "page-size": min(max_articles, 50),  # Guardian max is 50 per page
                "from-date": from_date,
                "show-fields": "headline,byline,body,thumbnail,trailText",
                "show-tags": "keyword",
                "order-by": "newest"
            }

            if query:
                params["q"] = query
            if section:
                params["section"] = section

            logger.info(f"Fetching articles from Guardian API (query={query}, section={section})")

            response = requests.get(
                f"{self.base_url}/search", params=params, timeout=15
            )
            response.raise_for_status()

            data = response.json()
            response_data = data.get("response", {})

            if response_data.get("status") == "ok":
                results = response_data.get("results", [])
                logger.info(f"Guardian API returned {len(results)} articles")

                for item in results:
                    article = self._parse_guardian_article(item)
                    if article:
                        articles.append(article)

            return articles

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Guardian API rate limit exceeded")
            elif e.response.status_code in (401, 403):
                logger.error("Guardian API authentication failed")
            else:
                logger.error(f"Guardian API HTTP error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error collecting news from Guardian: {str(e)}")
            return []

    def _parse_guardian_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse a Guardian API result into a NewsArticle object."""
        try:
            title = item.get("webTitle", "").strip()
            if not title:
                return None

            web_url = item.get("webUrl", "")
            article_id = f"guardian_{str(uuid.uuid5(uuid.NAMESPACE_URL, web_url))}"

            fields = item.get("fields", {})
            body = fields.get("body", "")
            trail_text = fields.get("trailText", "")
            byline = fields.get("byline", "")

            # Strip HTML tags from body for plain text content
            import re
            content = re.sub(r'<[^>]+>', '', body) if body else trail_text
            summary = re.sub(r'<[^>]+>', '', trail_text) if trail_text else content[:300]

            # Parse date
            published_at = None
            pub_date_str = item.get("webPublicationDate")
            if pub_date_str:
                try:
                    published_at = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Extract tags
            tags = []
            for tag in item.get("tags", []):
                tag_title = tag.get("webTitle", "")
                if tag_title:
                    tags.append(tag_title)

            section = item.get("sectionName", "general")

            article = NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                source_name="The Guardian",
                collector="Guardian API",
                url=web_url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                who=[byline] if byline else [],
                tags=tags[:10],
                category=section.lower() if section else "general"
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing Guardian article: {str(e)}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get collector status."""
        status = super().get_status()
        status["api_key_configured"] = bool(self.api_key and self.api_key != "your_guardian_api_key_here")
        return status
