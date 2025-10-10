"""
Web Scraper Collector for extracting news articles from web pages using newspaper3k.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlparse
import hashlib

try:
    from newspaper import Article as NewspaperArticle, Config as NewspaperConfig
    from newspaper import build as build_source
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    NewspaperArticle = None
    NewspaperConfig = None
    build_source = None

try:
    import requests
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    requests = None
    BeautifulSoup = None

from .base_collector import BaseCollector
from ..models.news_models import NewsSource, NewsArticle, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class WebScraperCollector(BaseCollector):
    """Collector for web scraping news articles from any website."""

    def __init__(self, source: NewsSource):
        """
        Initialize Web Scraper collector.

        Args:
            source: NewsSource configuration for web scraping
        """
        super().__init__(source)

        if not NEWSPAPER_AVAILABLE:
            logger.error("Newspaper3k library not available. Install with: pip install newspaper3k")
            self.enabled = False
            return

        if not BS4_AVAILABLE:
            logger.warning("BeautifulSoup not available. Some features may be limited.")

        # Configure newspaper3k
        self.config = NewspaperConfig()
        self.config.browser_user_agent = settings.USER_AGENT
        self.config.request_timeout = settings.REQUEST_TIMEOUT
        self.config.number_threads = 3
        self.config.fetch_images = False  # Don't download images for faster processing
        self.config.memoize_articles = True  # Cache articles
        self.config.language = 'en'

        self.enabled = True
        logger.info("Web Scraper collector initialized successfully")

    async def validate_source(self) -> bool:
        """Validate web scraper source configuration."""
        if not NEWSPAPER_AVAILABLE:
            logger.error("Newspaper3k library not installed")
            return False

        if not self.enabled:
            logger.error("Web scraper not enabled")
            return False

        try:
            # Test by fetching the source URL
            response = requests.get(
                self.source.url,
                headers={'User-Agent': settings.USER_AGENT},
                timeout=settings.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                logger.info(f"Web scraper source validated: {self.source.url}")
                return True
            else:
                logger.error(f"Web scraper source returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error validating web scraper source: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """
        Collect news articles from web source.

        Returns:
            List of NewsArticle objects
        """
        if not self.enabled:
            logger.warning("Web scraper not available")
            return []

        articles = []

        try:
            # Method 1: Use newspaper's build function to get all articles from a source
            if hasattr(self.source, 'use_newspaper_build') and self.source.use_newspaper_build:
                articles = await self._collect_with_newspaper_build()

            # Method 2: Scrape specific URLs provided
            elif hasattr(self.source, 'article_urls') and self.source.article_urls:
                articles = await self._collect_from_urls(self.source.article_urls)

            # Method 3: Scrape from homepage and extract article links
            else:
                articles = await self._collect_from_homepage()

            logger.info(f"Collected {len(articles)} articles from web scraper")
            return articles[:self.source.max_articles]

        except Exception as e:
            logger.error(f"Error collecting news from web scraper: {str(e)}")
            return []

    async def _collect_with_newspaper_build(self) -> List[NewsArticle]:
        """
        Use newspaper3k's build function to get all articles from a news source.

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            logger.info(f"Building source: {self.source.url}")

            # Build the news source
            news_source = build_source(self.source.url, config=self.config, memoize_articles=True)

            # Download articles (this discovers all article URLs)
            news_source.download_articles()
            news_source.parse_articles()

            logger.info(f"Found {news_source.size()} articles from {self.source.url}")

            # Process articles
            for article in news_source.articles[:self.source.max_articles]:
                try:
                    parsed_article = self._parse_newspaper_article(article)
                    if parsed_article:
                        articles.append(parsed_article)
                except Exception as e:
                    logger.warning(f"Error parsing article {article.url}: {str(e)}")
                    continue

            return articles

        except Exception as e:
            logger.error(f"Error building news source: {str(e)}")
            return []

    async def _collect_from_urls(self, urls: List[str]) -> List[NewsArticle]:
        """
        Scrape articles from a list of specific URLs.

        Args:
            urls: List of article URLs to scrape

        Returns:
            List of NewsArticle objects
        """
        articles = []

        for url in urls[:self.source.max_articles]:
            try:
                article = await self._scrape_article(url)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(f"Error scraping URL {url}: {str(e)}")
                continue

        return articles

    async def _collect_from_homepage(self) -> List[NewsArticle]:
        """
        Scrape homepage to find article links, then scrape those articles.

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            if not BS4_AVAILABLE:
                logger.error("BeautifulSoup required for homepage scraping")
                return []

            # Get homepage
            response = requests.get(
                self.source.url,
                headers={'User-Agent': settings.USER_AGENT},
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract article links
            article_urls = set()

            # Find all links that might be articles
            for link in soup.find_all('a', href=True):
                href = link['href']

                # Skip non-article links
                if any(skip in href.lower() for skip in ['#', 'javascript:', 'mailto:', '/tag/', '/category/', '/author/']):
                    continue

                # Make absolute URL
                if href.startswith('/'):
                    parsed_source = urlparse(self.source.url)
                    href = f"{parsed_source.scheme}://{parsed_source.netloc}{href}"
                elif not href.startswith('http'):
                    continue

                # Only include URLs from the same domain
                if urlparse(href).netloc == urlparse(self.source.url).netloc:
                    article_urls.add(href)

            logger.info(f"Found {len(article_urls)} potential article URLs on homepage")

            # Scrape articles
            for url in list(article_urls)[:self.source.max_articles]:
                try:
                    article = await self._scrape_article(url)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error scraping article {url}: {str(e)}")
                    continue

            return articles

        except Exception as e:
            logger.error(f"Error collecting from homepage: {str(e)}")
            return []

    async def _scrape_article(self, url: str) -> Optional[NewsArticle]:
        """
        Scrape a single article from a URL using newspaper3k.

        Args:
            url: Article URL

        Returns:
            NewsArticle object or None
        """
        try:
            # Create newspaper Article object
            article = NewspaperArticle(url, config=self.config)

            # Download and parse
            article.download()
            article.parse()

            # Try to extract additional info with NLP
            try:
                article.nlp()
            except:
                pass  # NLP is optional

            return self._parse_newspaper_article(article)

        except Exception as e:
            logger.error(f"Error scraping article {url}: {str(e)}")
            return None

    def _parse_newspaper_article(
        self,
        article: Any
    ) -> Optional[NewsArticle]:
        """
        Parse a newspaper3k Article into NewsArticle object.

        Args:
            article: newspaper3k Article object

        Returns:
            NewsArticle object or None
        """
        try:
            # Check if article has required content
            if not article.title or not article.text:
                logger.debug(f"Article missing required content: {article.url}")
                return None

            # Generate unique ID from URL
            article_id = f"web_{hashlib.md5(article.url.encode()).hexdigest()}"

            # Get article content
            title = article.title
            content = article.text
            summary = article.summary if hasattr(article, 'summary') and article.summary else content[:500]

            # Get metadata
            authors = article.authors if hasattr(article, 'authors') else []
            keywords = article.keywords if hasattr(article, 'keywords') else []
            tags = article.tags if hasattr(article, 'tags') else []

            # Combine keywords and tags
            all_tags = list(set(keywords + tags))

            # Get publish date
            published_at = article.publish_date
            if published_at:
                if not published_at.tzinfo:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            else:
                published_at = datetime.now(timezone.utc)

            # Get top image
            top_image = article.top_image if hasattr(article, 'top_image') else None

            # Get source name from domain
            domain = urlparse(article.url).netloc
            source_name = domain.replace('www.', '').split('.')[0].title()

            # Create NewsArticle
            news_article = NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                source=self.source.name,
                source_name=source_name,
                url=article.url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                tags=all_tags,
                category=getattr(self.source, 'category', 'general'),
                metadata={
                    "platform": "web",
                    "domain": domain,
                    "authors": authors,
                    "top_image": top_image,
                    "word_count": len(content.split()),
                    "scraped_with": "newspaper3k"
                }
            )

            return news_article

        except Exception as e:
            logger.error(f"Error parsing newspaper article: {str(e)}")
            return None

    async def scrape_single_url(self, url: str) -> Optional[NewsArticle]:
        """
        Public method to scrape a single URL.

        Args:
            url: Article URL to scrape

        Returns:
            NewsArticle object or None
        """
        return await self._scrape_article(url)

    def get_collector_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        stats = super().get_collector_stats()

        stats.update({
            "enabled": self.enabled,
            "newspaper3k_available": NEWSPAPER_AVAILABLE,
            "beautifulsoup_available": BS4_AVAILABLE,
            "user_agent": settings.USER_AGENT,
            "request_timeout": settings.REQUEST_TIMEOUT
        })

        return stats
