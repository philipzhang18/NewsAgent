"""
Unit tests for Twitter collector.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from src.collectors.twitter_collector import TwitterCollector
from src.models.news_models import NewsSource, SourceType


@pytest.fixture
def twitter_source():
    """Create a test Twitter source."""
    return NewsSource(
        name="Test Twitter",
        url="https://twitter.com",
        source_type=SourceType.SOCIAL,
        search_queries=["test query"],
        max_articles=10
    )


@pytest.fixture
def twitter_collector(twitter_source):
    """Create a Twitter collector instance."""
    with patch('src.collectors.twitter_collector.tweepy'):
        collector = TwitterCollector(twitter_source)
        return collector


class TestTwitterCollector:
    """Test cases for TwitterCollector."""

    def test_initialization_no_tweepy(self, twitter_source):
        """Test initialization when tweepy is not available."""
        with patch('src.collectors.twitter_collector.TWEEPY_AVAILABLE', False):
            collector = TwitterCollector(twitter_source)
            assert collector.client is None

    @patch('src.collectors.twitter_collector.tweepy')
    def test_initialization_with_bearer_token(self, mock_tweepy, twitter_source):
        """Test initialization with bearer token."""
        with patch('src.config.settings.settings.TWITTER_BEARER_TOKEN', 'test_token'):
            collector = TwitterCollector(twitter_source)
            assert collector.client is not None

    @patch('src.collectors.twitter_collector.tweepy')
    @pytest.mark.asyncio
    async def test_validate_source_success(self, mock_tweepy, twitter_collector):
        """Test successful source validation."""
        mock_client = Mock()
        mock_user = Mock()
        mock_user.data.username = "testuser"
        mock_client.get_me.return_value = mock_user
        twitter_collector.client = mock_client

        result = await twitter_collector.validate_source()
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_source_no_client(self, twitter_collector):
        """Test source validation without client."""
        twitter_collector.client = None
        result = await twitter_collector.validate_source()
        assert result is False

    @patch('src.collectors.twitter_collector.tweepy')
    @pytest.mark.asyncio
    async def test_collect_news_no_client(self, mock_tweepy, twitter_collector):
        """Test collecting news without client."""
        twitter_collector.client = None
        articles = await twitter_collector.collect_news()
        assert articles == []

    @patch('src.collectors.twitter_collector.tweepy')
    @pytest.mark.asyncio
    async def test_search_tweets(self, mock_tweepy, twitter_collector):
        """Test searching tweets."""
        # Create mock tweet
        mock_tweet = Mock()
        mock_tweet.id = "123456789"
        mock_tweet.text = "Test tweet content"
        mock_tweet.created_at = datetime.now(timezone.utc)
        mock_tweet.author_id = "user123"
        mock_tweet.public_metrics = {
            'like_count': 10,
            'retweet_count': 5,
            'reply_count': 2
        }

        # Create mock response
        mock_response = Mock()
        mock_response.data = [mock_tweet]
        mock_response.includes = {
            'users': [Mock(id="user123", username="testuser", name="Test User")]
        }

        mock_client = Mock()
        mock_client.search_recent_tweets.return_value = mock_response
        twitter_collector.client = mock_client

        articles = await twitter_collector._search_tweets("test query", max_results=10)

        assert len(articles) > 0
        assert articles[0].title.startswith("Tweet by @testuser")

    def test_parse_tweet(self, twitter_collector):
        """Test parsing a tweet into NewsArticle."""
        mock_tweet = Mock()
        mock_tweet.id = "123456789"
        mock_tweet.text = "Test tweet content"
        mock_tweet.created_at = datetime.now(timezone.utc)
        mock_tweet.author_id = "user123"
        mock_tweet.public_metrics = {
            'like_count': 10,
            'retweet_count': 5,
            'reply_count': 2
        }
        mock_tweet.entities = {
            'hashtags': [{'tag': 'test'}, {'tag': 'news'}]
        }

        mock_user = Mock()
        mock_user.username = "testuser"
        mock_user.name = "Test User"
        mock_user.verified = True

        users = {"user123": mock_user}

        article = twitter_collector._parse_tweet(mock_tweet, users, "test query")

        assert article is not None
        assert article.source_name == "Twitter/@testuser"
        assert "test" in article.tags
        assert article.metadata['likes'] == 10
        assert article.metadata['verified'] is True

    def test_get_collector_stats_with_client(self, twitter_collector):
        """Test getting collector stats with active client."""
        twitter_collector.client = Mock()
        stats = twitter_collector.get_collector_stats()

        assert stats['api_available'] is True
        assert 'api_version' in stats

    def test_get_collector_stats_without_client(self, twitter_collector):
        """Test getting collector stats without client."""
        twitter_collector.client = None
        stats = twitter_collector.get_collector_stats()

        assert stats['api_available'] is False
        assert 'error' in stats
