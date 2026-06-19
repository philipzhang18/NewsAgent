import os
from dotenv import load_dotenv
from typing import List

load_dotenv(override=True)


class Settings:
    """Application settings and configuration."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", os.getenv("base_url", ""))

    # News API Keys
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    GUARDIAN_API_KEY: str = os.getenv("GUARDIAN_API_KEY", "")
    NYTIMES_API_KEY: str = os.getenv("NYTIMES_API_KEY", "")

    # Social Media API Keys
    TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET: str = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "")

    # Local SQLite storage
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "data/news_articles.db")

    # Application Settings
    FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")

    # News Collection Settings
    COLLECTION_INTERVAL: int = int(os.getenv("COLLECTION_INTERVAL", "300"))
    MAX_ARTICLES_PER_SOURCE: int = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "100"))
    ENABLE_SENTIMENT_ANALYSIS: bool = os.getenv("ENABLE_SENTIMENT_ANALYSIS", "True").lower() == "true"
    ENABLE_BIAS_DETECTION: bool = os.getenv("ENABLE_BIAS_DETECTION", "True").lower() == "true"

    # RSS Feed Sources
    RSS_FEEDS: List[str] = os.getenv("RSS_FEEDS", "").split(",") if os.getenv("RSS_FEEDS") else []

    # Web Scraping Settings
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_PROCESS_PER_COLLECTION: int = int(os.getenv("MAX_PROCESS_PER_COLLECTION", "30"))

    @classmethod
    def validate(cls) -> bool:
        """Validate required settings."""
        if not cls.OPENAI_API_KEY:
            print("Missing required environment variable: OPENAI_API_KEY")
            return False

        if cls.FLASK_SECRET_KEY == "dev-secret-key" and not cls.DEBUG:
            print("Warning: using default FLASK_SECRET_KEY in non-debug mode")

        return True


settings = Settings()
