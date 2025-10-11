#!/usr/bin/env python
"""
MongoDB database initialization script.
Creates collections, indexes, and initial data.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING, TEXT
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_mongodb():
    """Initialize MongoDB database with collections and indexes."""

    # Connect to MongoDB
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    client = MongoClient(mongodb_uri)

    # Get database
    db_name = mongodb_uri.split('/')[-1] if '/' in mongodb_uri else 'news_agent'
    db = client[db_name]

    logger.info(f"Initializing database: {db_name}")

    # 1. Articles Collection
    logger.info("Creating articles collection...")
    articles = db['articles']
    articles_indexes = [
        IndexModel([('id', ASCENDING)], unique=True),
        IndexModel([('url', ASCENDING)], unique=True),
        IndexModel([('collected_at', DESCENDING)]),
        IndexModel([('published_at', DESCENDING)]),
        IndexModel([('source_name', ASCENDING)]),
        IndexModel([('sentiment', ASCENDING)]),
        IndexModel([('is_processed', ASCENDING)]),
        IndexModel([('title', TEXT), ('content', TEXT), ('keywords', TEXT)]),  # Full-text search
    ]
    articles.create_indexes(articles_indexes)
    logger.info(f"✓ Created {len(articles_indexes)} indexes for articles collection")

    # 2. Sources Collection
    logger.info("Creating sources collection...")
    sources = db['sources']
    sources_indexes = [
        IndexModel([('id', ASCENDING)], unique=True),
        IndexModel([('name', ASCENDING)]),
        IndexModel([('type', ASCENDING)]),
        IndexModel([('is_active', ASCENDING)]),
    ]
    sources.create_indexes(sources_indexes)
    logger.info(f"✓ Created {len(sources_indexes)} indexes for sources collection")

    # Insert default sources if collection is empty
    if sources.count_documents({}) == 0:
        default_sources = [
            {
                'id': 'newsapi',
                'name': 'NewsAPI',
                'type': 'api',
                'url': 'https://newsapi.org',
                'is_active': True,
                'config': {'country': 'us', 'page_size': 100},
                'created_at': datetime.now(timezone.utc)
            },
            {
                'id': 'rss_tech',
                'name': 'TechCrunch RSS',
                'type': 'rss',
                'url': 'https://techcrunch.com/feed/',
                'is_active': True,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'id': 'rss_business',
                'name': 'BBC Business RSS',
                'type': 'rss',
                'url': 'https://feeds.bbci.co.uk/news/business/rss.xml',
                'is_active': True,
                'created_at': datetime.now(timezone.utc)
            },
            {
                'id': 'twitter',
                'name': 'Twitter/X',
                'type': 'social',
                'platform': 'twitter',
                'is_active': False,  # Requires API keys
                'created_at': datetime.now(timezone.utc)
            },
            {
                'id': 'reddit',
                'name': 'Reddit',
                'type': 'social',
                'platform': 'reddit',
                'is_active': False,  # Requires API keys
                'created_at': datetime.now(timezone.utc)
            }
        ]
        sources.insert_many(default_sources)
        logger.info(f"✓ Inserted {len(default_sources)} default sources")

    # 3. Collections (batches) Collection
    logger.info("Creating collections collection...")
    collections = db['collections']
    collections_indexes = [
        IndexModel([('id', ASCENDING)], unique=True),
        IndexModel([('source_id', ASCENDING)]),
        IndexModel([('collected_at', DESCENDING)]),
        IndexModel([('status', ASCENDING)]),
    ]
    collections.create_indexes(collections_indexes)
    logger.info(f"✓ Created {len(collections_indexes)} indexes for collections collection")

    # 4. API Keys Collection (for authentication)
    logger.info("Creating api_keys collection...")
    api_keys = db['api_keys']
    api_keys_indexes = [
        IndexModel([('key_hash', ASCENDING)], unique=True),
        IndexModel([('created_at', DESCENDING)]),
        IndexModel([('is_active', ASCENDING)]),
    ]
    api_keys.create_indexes(api_keys_indexes)
    logger.info(f"✓ Created {len(api_keys_indexes)} indexes for api_keys collection")

    # 5. Alerts Collection
    logger.info("Creating alerts collection...")
    alerts = db['alerts']
    alerts_indexes = [
        IndexModel([('created_at', DESCENDING)]),
        IndexModel([('severity', ASCENDING)]),
        IndexModel([('resolved', ASCENDING)]),
        IndexModel([('component', ASCENDING)]),
    ]
    alerts.create_indexes(alerts_indexes)
    logger.info(f"✓ Created {len(alerts_indexes)} indexes for alerts collection")

    # 6. Metrics Collection
    logger.info("Creating metrics collection...")
    metrics = db['metrics']
    metrics_indexes = [
        IndexModel([('timestamp', DESCENDING)]),
        IndexModel([('metric_name', ASCENDING)]),
        IndexModel([('timestamp', DESCENDING), ('metric_name', ASCENDING)]),
    ]
    metrics.create_indexes(metrics_indexes)
    logger.info(f"✓ Created {len(metrics_indexes)} indexes for metrics collection")

    # Display database stats
    logger.info("\n" + "="*50)
    logger.info("Database Initialization Complete!")
    logger.info("="*50)
    logger.info(f"Database: {db_name}")
    logger.info(f"Collections created: {len(db.list_collection_names())}")
    logger.info("\nCollections:")
    for coll_name in db.list_collection_names():
        count = db[coll_name].count_documents({})
        indexes = len(db[coll_name].list_indexes())
        logger.info(f"  • {coll_name}: {count} documents, {indexes} indexes")

    client.close()
    logger.info("\n✓ MongoDB initialization successful!")


if __name__ == '__main__':
    init_mongodb()
