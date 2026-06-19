# News collectors package
from .base_collector import BaseCollector
from .rss_collector import RSSCollector
from .newsapi_collector import NewsAPICollector
from .guardian_collector import GuardianCollector
from .nytimes_collector import NYTimesCollector
from .reddit_collector import RedditCollector

__all__ = [
    "BaseCollector",
    "RSSCollector",
    "NewsAPICollector",
    "GuardianCollector",
    "NYTimesCollector",
    "RedditCollector",
]
