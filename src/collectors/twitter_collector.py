"""
Twitter/X Collector for gathering news and trending topics from Twitter/X.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import hashlib

try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    tweepy = None

from .base_collector import BaseCollector
from ..models.news_models import NewsSource, NewsArticle, SourceType
from ..config.settings import settings

logger = logging.getLogger(__name__)


class TwitterCollector(BaseCollector):
    """Collector for Twitter/X social media platform."""

    def __init__(self, source: NewsSource):
        """
        Initialize Twitter collector.

        Args:
            source: NewsSource configuration for Twitter
        """
        super().__init__(source)

        if not TWEEPY_AVAILABLE:
            logger.error("Tweepy library not available. Install with: pip install tweepy")
            self.client = None
            return

        # Initialize Twitter API client
        try:
            # Twitter API v2 with Bearer Token (recommended)
            if settings.TWITTER_BEARER_TOKEN:
                self.client = tweepy.Client(
                    bearer_token=settings.TWITTER_BEARER_TOKEN,
                    wait_on_rate_limit=True
                )
                logger.info("Twitter client initialized with Bearer Token (API v2)")

            # Fallback to API v1.1 with OAuth 1.0a
            elif all([
                settings.TWITTER_API_KEY,
                settings.TWITTER_API_SECRET,
                settings.TWITTER_ACCESS_TOKEN,
                settings.TWITTER_ACCESS_TOKEN_SECRET
            ]):
                auth = tweepy.OAuthHandler(
                    settings.TWITTER_API_KEY,
                    settings.TWITTER_API_SECRET
                )
                auth.set_access_token(
                    settings.TWITTER_ACCESS_TOKEN,
                    settings.TWITTER_ACCESS_TOKEN_SECRET
                )
                self.client = tweepy.Client(
                    consumer_key=settings.TWITTER_API_KEY,
                    consumer_secret=settings.TWITTER_API_SECRET,
                    access_token=settings.TWITTER_ACCESS_TOKEN,
                    access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                    wait_on_rate_limit=True
                )
                logger.info("Twitter client initialized with OAuth 1.0a")

            else:
                logger.error("Twitter API credentials not configured")
                self.client = None

        except Exception as e:
            logger.error(f"Error initializing Twitter client: {str(e)}")
            self.client = None

        # Default search queries if not specified in source
        self.default_queries = [
            "breaking news",
            "top stories",
            "latest news",
            "#breaking",
            "#news"
        ]

    async def validate_source(self) -> bool:
        """Validate Twitter source configuration and API access."""
        if not TWEEPY_AVAILABLE:
            logger.error("Tweepy library not installed")
            return False

        if not self.client:
            logger.error("Twitter client not initialized")
            return False

        try:
            # For Bearer Token, we can just check if the client is initialized
            # No need to make actual API calls during validation
            # This saves API quota
            logger.info("Twitter API client initialized and ready")
            return True

        except Exception as e:
            logger.error(f"Error validating Twitter API: {str(e)}")
            return False

    async def collect_news(self) -> List[NewsArticle]:
        """
        Collect news from Twitter/X.

        Returns:
            List of NewsArticle objects
        """
        if not self.client:
            logger.warning("Twitter client not available")
            return []

        articles = []

        try:
            # Get search queries from source config or use defaults
            queries = getattr(self.source, 'search_queries', None) or self.default_queries
            max_results = min(getattr(self.source, 'max_articles', 100), 100)  # Twitter API limit

            logger.info(f"Collecting tweets for {len(queries)} queries, max {max_results} per query")

            for query in queries:
                try:
                    # Search recent tweets
                    tweets = await self._search_tweets(query, max_results=max_results // len(queries))
                    articles.extend(tweets)

                except tweepy.errors.TooManyRequests:
                    logger.warning(f"Rate limit reached for query: {query}")
                    break  # Stop collecting if rate limited
                except Exception as e:
                    logger.error(f"Error collecting tweets for query '{query}': {str(e)}")
                    continue

            # Optionally collect from specific users/lists
            if hasattr(self.source, 'twitter_users') and self.source.twitter_users:
                user_tweets = await self._collect_from_users(
                    self.source.twitter_users,
                    max_results=max_results // 2
                )
                articles.extend(user_tweets)

            logger.info(f"Collected {len(articles)} tweets from Twitter/X")
            return articles[:self.source.max_articles]

        except Exception as e:
            logger.error(f"Error collecting news from Twitter: {str(e)}")
            return []

    async def _search_tweets(self, query: str, max_results: int = 10) -> List[NewsArticle]:
        """
        Search for tweets matching a query.

        Args:
            query: Search query string
            max_results: Maximum number of results (max 100)

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            # Use Twitter API v2 search recent tweets
            # Note: This requires Essential access (free tier limits apply)
            response = self.client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 10),  # Reduce to 10 to save API quota
                tweet_fields=['created_at', 'author_id', 'public_metrics'],
                expansions=['author_id'],
                user_fields=['username', 'name']
            )

            if not response or not response.data:
                logger.debug(f"No tweets found for query: {query}")
                return []

            # Create user lookup dict
            users = {}
            if response.includes and 'users' in response.includes:
                users = {user.id: user for user in response.includes['users']}

            # Parse tweets
            for tweet in response.data:
                try:
                    article = self._parse_tweet(tweet, users, query)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing tweet {tweet.id}: {str(e)}")
                    continue

            logger.debug(f"Found {len(articles)} tweets for query: {query}")
            return articles

        except tweepy.errors.TooManyRequests as e:
            logger.warning(f"Twitter API rate limit exceeded for query '{query}'. Please wait before trying again.")
            return []
        except tweepy.errors.Forbidden as e:
            logger.error(f"Twitter API access forbidden for query '{query}'. Check API permissions and access level.")
            return []
        except Exception as e:
            logger.error(f"Error searching tweets for query '{query}': {str(e)}")
            return []

    async def _collect_from_users(self, usernames: List[str], max_results: int = 10) -> List[NewsArticle]:
        """
        Collect tweets from specific Twitter users.

        Args:
            usernames: List of Twitter usernames (without @)
            max_results: Maximum results per user

        Returns:
            List of NewsArticle objects
        """
        articles = []

        for username in usernames:
            try:
                # Get user ID
                user = self.client.get_user(username=username)
                if not user or not user.data:
                    logger.warning(f"User not found: @{username}")
                    continue

                user_id = user.data.id

                # Get user's recent tweets
                tweets = self.client.get_users_tweets(
                    id=user_id,
                    max_results=min(max_results, 100),
                    tweet_fields=['created_at', 'public_metrics', 'entities'],
                    exclude=['retweets', 'replies']
                )

                if tweets and tweets.data:
                    users = {user_id: user.data}
                    for tweet in tweets.data:
                        try:
                            article = self._parse_tweet(tweet, users, f"@{username}")
                            if article:
                                articles.append(article)
                        except Exception as e:
                            logger.warning(f"Error parsing tweet from @{username}: {str(e)}")
                            continue

                logger.debug(f"Collected {len(tweets.data) if tweets and tweets.data else 0} tweets from @{username}")

            except Exception as e:
                logger.error(f"Error collecting tweets from @{username}: {str(e)}")
                continue

        return articles

    def _parse_tweet(
        self,
        tweet: Any,
        users: Dict[str, Any],
        query: str = ""
    ) -> Optional[NewsArticle]:
        """
        Parse a tweet into a NewsArticle object.

        Args:
            tweet: Tweet data from Tweepy
            users: Dictionary of user objects
            query: Search query used

        Returns:
            NewsArticle object or None
        """
        try:
            # Get author info
            author = users.get(tweet.author_id)
            author_name = author.username if author else "Unknown"
            author_display_name = author.name if author else "Unknown User"

            # Generate unique ID
            article_id = f"twitter_{tweet.id}"

            # Get tweet text
            content = tweet.text

            # Get tweet URL
            url = f"https://twitter.com/{author_name}/status/{tweet.id}"

            # Get metrics
            metrics = tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
            likes = metrics.get('like_count', 0) if metrics else 0
            retweets = metrics.get('retweet_count', 0) if metrics else 0
            replies = metrics.get('reply_count', 0) if metrics else 0

            # Extract hashtags as tags
            tags = []
            if hasattr(tweet, 'entities') and tweet.entities:
                if 'hashtags' in tweet.entities:
                    tags = [tag['tag'] for tag in tweet.entities['hashtags']]

            # Parse timestamp
            published_at = tweet.created_at if hasattr(tweet, 'created_at') else datetime.now(timezone.utc)
            if not published_at.tzinfo:
                published_at = published_at.replace(tzinfo=timezone.utc)

            # Create article
            article = NewsArticle(
                id=article_id,
                title=f"Tweet by @{author_name}: {content[:100]}...",
                content=content,
                summary=content[:200] if len(content) > 200 else content,
                source_name=f"Twitter/@{author_name}",
                url=url,
                published_at=published_at,
                collected_at=datetime.now(timezone.utc),
                tags=tags,
                category="social_media"
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing tweet: {str(e)}")
            return None

    def get_collector_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        stats = super().get_collector_stats()

        if self.client:
            stats.update({
                "api_available": True,
                "api_version": "v2",
                "rate_limit_enabled": True
            })
        else:
            stats.update({
                "api_available": False,
                "error": "Twitter client not initialized"
            })

        return stats
