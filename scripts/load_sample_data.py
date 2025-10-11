#!/usr/bin/env python
"""
Load sample data into the database for testing and demonstration.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.sample_data import SAMPLE_ARTICLES, SAMPLE_SOURCES
from src.services.storage_service import storage_service
from src.models.news_models import NewsArticle, NewsSource, SentimentType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_sample_data():
    """Load sample data into database."""

    logger.info("Loading sample data...")

    # Load sample articles
    logger.info(f"Loading {len(SAMPLE_ARTICLES)} sample articles...")
    for article_data in SAMPLE_ARTICLES:
        article = NewsArticle(
            id=article_data['id'],
            title=article_data['title'],
            content=article_data['content'],
            url=article_data['url'],
            source_name=article_data['source_name'],
            author=article_data.get('author'),
            published_at=datetime.fromisoformat(article_data['published_at'].replace('Z', '+00:00')),
            collected_at=datetime.fromisoformat(article_data['collected_at'].replace('Z', '+00:00')),
            category=article_data.get('category'),
            keywords=article_data.get('keywords', []),
            sentiment=SentimentType(article_data.get('sentiment', 'neutral')),
            sentiment_score=article_data.get('sentiment_score', 0.0),
            bias_score=article_data.get('bias_score', 0.0),
            is_processed=article_data.get('is_processed', False),
            summary=article_data.get('summary')
        )

        try:
            await storage_service.save_article(article)
            logger.info(f"  ✓ Loaded article: {article.title[:50]}...")
        except Exception as e:
            logger.warning(f"  ✗ Skipped article (may already exist): {article.title[:50]}... - {e}")

    logger.info("\n" + "="*50)
    logger.info("Sample Data Loading Complete!")
    logger.info("="*50)
    logger.info(f"Articles loaded: {len(SAMPLE_ARTICLES)}")
    logger.info("\nYou can now:")
    logger.info("  • View articles at http://localhost:5000/articles")
    logger.info("  • Access dashboard at http://localhost:5000/dashboard/")
    logger.info("  • Test search functionality")
    logger.info("\n✓ Sample data ready for use!")


if __name__ == '__main__':
    asyncio.run(load_sample_data())
