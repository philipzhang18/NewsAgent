"""
Celery tasks for news collection, processing, and storage operations.
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

from src.celery_app import celery_app
from src.services.news_collector_service import news_collector_service
from src.services.news_processor_service import processor_service
from src.services.storage_service import storage_service
from src.models.news_models import NewsArticle

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name='src.tasks.news_tasks.collect_news_task',
    bind=True,
    queue='collection'
)
def collect_news_task(self, source_ids: Optional[List[str]] = None, limit: int = 100):
    """
    Collect news from configured sources.

    Args:
        source_ids: Optional list of source IDs to collect from
        limit: Maximum number of articles to collect per source

    Returns:
        Dictionary with collection results
    """
    logger.info(f"Starting news collection task: source_ids={source_ids}, limit={limit}")

    try:
        async def _collect():
            # Initialize collector if not running
            if not news_collector_service.is_running:
                await news_collector_service.initialize()

            # Collect from all or specific sources
            if source_ids:
                results = []
                for source_id in source_ids:
                    articles = await news_collector_service.collect_from_source(source_id, limit=limit)
                    results.extend(articles)
            else:
                results = await news_collector_service.collect_all(limit_per_source=limit)

            return results

        # Run collection
        articles = run_async(_collect())

        # Queue articles for processing
        if articles:
            article_ids = [article.id for article in articles]
            logger.info(f"Collected {len(articles)} articles, queueing for processing")

            # Queue processing tasks
            for article in articles:
                process_article_task.apply_async(
                    args=[article.to_dict()],
                    queue='processing'
                )

        return {
            'success': True,
            'collected': len(articles),
            'article_ids': article_ids if articles else [],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"News collection task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)  # Retry after 1 minute


@celery_app.task(
    name='src.tasks.news_tasks.process_article_task',
    bind=True,
    queue='processing'
)
def process_article_task(self, article_data: Dict, save_to_db: bool = True):
    """
    Process a single news article.

    Args:
        article_data: Article data dictionary
        save_to_db: Whether to save to database after processing

    Returns:
        Processed article data
    """
    logger.info(f"Processing article: {article_data.get('id')}")

    try:
        async def _process():
            # Convert dict to NewsArticle
            article = NewsArticle.from_dict(article_data)

            # Initialize processor if needed
            if not processor_service.is_running:
                await processor_service.start()

            # Process article
            processed = await processor_service.process_article(article, save_to_db=save_to_db)

            return processed

        # Run processing
        processed_article = run_async(_process())

        if processed_article and processed_article.is_processed:
            logger.info(f"Successfully processed article: {processed_article.id}")
            return {
                'success': True,
                'article_id': processed_article.id,
                'processed_at': processed_article.processed_at.isoformat() if processed_article.processed_at else None
            }
        else:
            logger.warning(f"Article processing incomplete: {article_data.get('id')}")
            return {
                'success': False,
                'article_id': article_data.get('id'),
                'error': 'Processing incomplete'
            }

    except Exception as e:
        logger.error(f"Article processing task failed: {str(e)}")
        raise self.retry(exc=e, countdown=30)  # Retry after 30 seconds


@celery_app.task(
    name='src.tasks.news_tasks.analyze_batch_task',
    bind=True,
    queue='analysis'
)
def analyze_batch_task(self, article_ids: List[str], analysis_types: Optional[List[str]] = None):
    """
    Analyze a batch of articles.

    Args:
        article_ids: List of article IDs to analyze
        analysis_types: Types of analysis to perform (sentiment, bias, etc.)

    Returns:
        Analysis results
    """
    logger.info(f"Analyzing batch of {len(article_ids)} articles")

    try:
        async def _analyze():
            results = []

            for article_id in article_ids:
                # Retrieve article
                article = await storage_service.get_article(article_id)

                if not article:
                    logger.warning(f"Article not found: {article_id}")
                    continue

                # Perform analysis if not already done
                if not article.is_processed:
                    processed = await processor_service.process_article(article, save_to_db=True)
                    results.append({
                        'article_id': article_id,
                        'processed': processed.is_processed,
                        'sentiment': processed.sentiment_score if hasattr(processed, 'sentiment_score') else None,
                        'bias': processed.bias_score if hasattr(processed, 'bias_score') else None
                    })

            return results

        # Run analysis
        results = run_async(_analyze())

        return {
            'success': True,
            'analyzed': len(results),
            'results': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Batch analysis task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(
    name='src.tasks.news_tasks.store_article_task',
    bind=True,
    queue='storage'
)
def store_article_task(self, article_data: Dict):
    """
    Store article to database.

    Args:
        article_data: Article data to store

    Returns:
        Storage result
    """
    logger.info(f"Storing article: {article_data.get('id')}")

    try:
        async def _store():
            article = NewsArticle.from_dict(article_data)
            success = await storage_service.save_article(article)
            return success

        # Run storage
        success = run_async(_store())

        return {
            'success': success,
            'article_id': article_data.get('id'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Article storage task failed: {str(e)}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(
    name='src.tasks.news_tasks.cleanup_old_data_task',
    bind=True,
    queue='default'
)
def cleanup_old_data_task(self, days_to_keep: int = 30):
    """
    Clean up old articles and data.

    Args:
        days_to_keep: Number of days of data to keep

    Returns:
        Cleanup results
    """
    logger.info(f"Starting cleanup of data older than {days_to_keep} days")

    try:
        async def _cleanup():
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            # Delete old articles
            deleted_count = await storage_service.delete_articles_before(cutoff_date)

            return deleted_count

        # Run cleanup
        deleted = run_async(_cleanup())

        logger.info(f"Cleanup completed: deleted {deleted} articles")

        return {
            'success': True,
            'deleted_count': deleted,
            'cutoff_date': (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@celery_app.task(
    name='src.tasks.news_tasks.bulk_reprocess_task',
    bind=True,
    queue='processing'
)
def bulk_reprocess_task(self, filters: Optional[Dict] = None, limit: int = 100):
    """
    Reprocess articles matching filters.

    Args:
        filters: Query filters for articles to reprocess
        limit: Maximum number of articles to reprocess

    Returns:
        Reprocessing results
    """
    logger.info(f"Starting bulk reprocessing with filters: {filters}")

    try:
        async def _reprocess():
            # Query articles
            articles = await storage_service.query_articles(filters or {}, limit=limit)

            # Queue for reprocessing
            for article in articles:
                process_article_task.apply_async(
                    args=[article.to_dict()],
                    kwargs={'save_to_db': True},
                    queue='processing'
                )

            return len(articles)

        # Run reprocessing
        count = run_async(_reprocess())

        return {
            'success': True,
            'queued_count': count,
            'filters': filters,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Bulk reprocess task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)
