"""
Reddit Collector for gathering news from Reddit communities and trending topics.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

try:
    import praw
    from praw.models import Submission
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    praw = None
    Submission = None

from .base_collector import BaseCollector
from ..models.news_models import NewsSource, NewsArticle, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    """Collector for Reddit social media platform."""

    def __init__(self, source: NewsSource):
        """
        Initialize Reddit collector.

        Args:
            source: NewsSource configuration for Reddit
        """
        super().__init__(source)

        if not PRAW_AVAILABLE:
            logger.error("PRAW library not available. Install with: pip install praw")
            self.reddit = None
            return

        # Initialize Reddit API client
        try:
            if not all([
                settings.REDDIT_CLIENT_ID,
                settings.REDDIT_CLIENT_SECRET,
                settings.REDDIT_USER_AGENT
            ]):
                logger.error("Reddit API credentials not configured")
                self.reddit = None
                return

            self.reddit = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT
            )

            logger.info("Reddit client initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing Reddit client: {str(e)}")
            self.reddit = None

        # Default subreddits if not specified
        self.default_subreddits = [
            "news",
            "worldnews",
            "politics",
            "technology",
            "science",
            "business"
        ]

    async def validate_source(self) -> bool:
        """Validate Reddit source configuration and API access."""
        if not PRAW_AVAILABLE:
            logger.error("PRAW library not installed")
            return False

        if not self.reddit:
            logger.error("Reddit client not initialized")
            return False

        try:
            # Test API access by checking if client is read-only
            logger.info(f"Reddit client read-only mode: {self.reddit.read_only}")

            # Try to access a subreddit to verify API works
            test_sub = self.reddit.subreddit("news")
            test_sub.id  # This will raise an exception if API access fails

            logger.info("Reddit API access validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error validating Reddit API: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """
        Collect news from Reddit.

        Returns:
            List of NewsArticle objects
        """
        if not self.reddit:
            logger.warning("Reddit client not available")
            return []

        articles = []

        try:
            # Get subreddits from source config or use defaults
            subreddits = getattr(self.source, 'subreddits', None) or self.default_subreddits
            max_results = getattr(self.source, 'max_articles', 100)

            # Get sorting method (hot, new, top, rising)
            sort_method = getattr(self.source, 'sort', 'hot')

            logger.info(f"Collecting posts from {len(subreddits)} subreddits, max {max_results} total")

            # Calculate posts per subreddit
            posts_per_sub = max(1, max_results // len(subreddits))

            for subreddit_name in subreddits:
                try:
                    posts = await self._collect_from_subreddit(
                        subreddit_name,
                        limit=posts_per_sub,
                        sort=sort_method
                    )
                    articles.extend(posts)

                except Exception as e:
                    logger.error(f"Error collecting from r/{subreddit_name}: {str(e)}")
                    continue

            logger.info(f"Collected {len(articles)} posts from Reddit")
            return articles[:self.source.max_articles]

        except Exception as e:
            logger.error(f"Error collecting news from Reddit: {str(e)}")
            return []

    async def _collect_from_subreddit(
        self,
        subreddit_name: str,
        limit: int = 25,
        sort: str = "hot"
    ) -> List[NewsArticle]:
        """
        Collect posts from a specific subreddit.

        Args:
            subreddit_name: Name of the subreddit (without r/)
            limit: Maximum number of posts to collect
            sort: Sorting method (hot, new, top, rising)

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get posts based on sort method
            if sort == "hot":
                submissions = subreddit.hot(limit=limit)
            elif sort == "new":
                submissions = subreddit.new(limit=limit)
            elif sort == "top":
                submissions = subreddit.top(time_filter="day", limit=limit)
            elif sort == "rising":
                submissions = subreddit.rising(limit=limit)
            else:
                logger.warning(f"Unknown sort method: {sort}, using 'hot'")
                submissions = subreddit.hot(limit=limit)

            # Parse submissions
            for submission in submissions:
                try:
                    article = self._parse_submission(submission, subreddit_name)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing submission {submission.id}: {str(e)}")
                    continue

            logger.debug(f"Collected {len(articles)} posts from r/{subreddit_name}")
            return articles

        except Exception as e:
            logger.error(f"Error collecting from r/{subreddit_name}: {str(e)}")
            return []

    def _parse_submission(
        self,
        submission: Any,
        subreddit_name: str
    ) -> Optional[NewsArticle]:
        """
        Parse a Reddit submission into a NewsArticle object.

        Args:
            submission: Reddit submission object from PRAW
            subreddit_name: Name of the subreddit

        Returns:
            NewsArticle object or None
        """
        try:
            # Generate unique ID
            article_id = f"reddit_{submission.id}"

            # Get submission content
            title = submission.title

            # Use selftext for text posts, or URL for link posts
            if submission.is_self:
                content = submission.selftext if submission.selftext else title
                url = f"https://reddit.com{submission.permalink}"
            else:
                content = f"Link post: {submission.url}\n\n{submission.selftext}" if submission.selftext else f"Link post: {submission.url}"
                url = submission.url

            # Create summary
            summary = content[:500] if len(content) > 500 else content

            # Get post flair as category
            category = submission.link_flair_text if hasattr(submission, 'link_flair_text') and submission.link_flair_text else "general"

            # Parse timestamp
            published_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

            # Get author
            author = str(submission.author) if submission.author else "[deleted]"

            # Create article
            article = NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                source=self.source.name,
                source_name=f"Reddit/r/{subreddit_name}",
                url=url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                tags=[subreddit_name],
                category=category,
                metadata={
                    "platform": "reddit",
                    "subreddit": subreddit_name,
                    "author": author,
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "is_self_post": submission.is_self,
                    "is_video": submission.is_video,
                    "over_18": submission.over_18,
                    "spoiler": submission.spoiler,
                    "stickied": submission.stickied,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "submission_id": submission.id
                }
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing Reddit submission: {str(e)}")
            return None

    async def search_subreddits(
        self,
        query: str,
        limit: int = 25,
        sort: str = "relevance"
    ) -> List[NewsArticle]:
        """
        Search across multiple subreddits.

        Args:
            query: Search query
            limit: Maximum number of results
            sort: Sorting method (relevance, hot, top, new)

        Returns:
            List of NewsArticle objects
        """
        if not self.reddit:
            return []

        articles = []

        try:
            subreddits = getattr(self.source, 'subreddits', None) or self.default_subreddits
            subreddit_str = "+".join(subreddits)

            subreddit = self.reddit.subreddit(subreddit_str)

            # Search submissions
            submissions = subreddit.search(
                query=query,
                sort=sort,
                time_filter="day",
                limit=limit
            )

            for submission in submissions:
                try:
                    # Extract subreddit name from submission
                    sub_name = str(submission.subreddit)
                    article = self._parse_submission(submission, sub_name)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing search result: {str(e)}")
                    continue

            logger.info(f"Found {len(articles)} posts for query: {query}")
            return articles

        except Exception as e:
            logger.error(f"Error searching Reddit: {str(e)}")
            return []

    def get_trending_topics(self, limit: int = 10) -> List[str]:
        """
        Get trending topics from Reddit.

        Args:
            limit: Maximum number of topics

        Returns:
            List of trending topic strings
        """
        if not self.reddit:
            return []

        try:
            # Get posts from r/all hot
            subreddit = self.reddit.subreddit("all")
            submissions = subreddit.hot(limit=limit)

            topics = []
            for submission in submissions:
                if submission.title:
                    topics.append(submission.title)

            return topics[:limit]

        except Exception as e:
            logger.error(f"Error getting trending topics: {str(e)}")
            return []

    def get_collector_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        stats = super().get_collector_stats()

        if self.reddit:
            stats.update({
                "api_available": True,
                "read_only": self.reddit.read_only,
                "default_subreddits": len(self.default_subreddits)
            })
        else:
            stats.update({
                "api_available": False,
                "error": "Reddit client not initialized"
            })

        return stats
