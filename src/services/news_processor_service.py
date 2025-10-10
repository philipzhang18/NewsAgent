"""
News Processor Service for coordinating article processing pipeline.

This service manages the processing workflow for collected news articles,
including content analysis, sentiment detection, bias scoring, and summarization.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timezone
from collections import deque
import time

from ..models.news_models import NewsArticle, NewsCollection
from ..processors.news_processor import NewsProcessor
from ..services.storage_service import storage_service
from ..services.cache_service import cache_service
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ProcessingQueueItem:
    """Represents an item in the processing queue."""

    def __init__(self, article: NewsArticle, priority: int = 0, retry_count: int = 0):
        self.article = article
        self.priority = priority
        self.retry_count = retry_count
        self.added_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None

    @property
    def processing_time(self) -> Optional[float]:
        """Calculate processing time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def wait_time(self) -> float:
        """Calculate wait time in seconds."""
        start = self.started_at or datetime.now(timezone.utc)
        return (start - self.added_at).total_seconds()


class NewsProcessorService:
    """Service for coordinating news article processing."""

    def __init__(self, max_workers: int = 5, max_retries: int = 3):
        """
        Initialize the news processor service.

        Args:
            max_workers: Maximum number of concurrent processing tasks
            max_retries: Maximum number of retry attempts for failed processing
        """
        self.processor = NewsProcessor()
        self.max_workers = max_workers
        self.max_retries = max_retries

        # Processing queue
        self.queue: deque = deque()
        self.processing: Dict[str, ProcessingQueueItem] = {}

        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "total_retries": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "queue_max_size": 0,
            "started_at": datetime.now(timezone.utc)
        }

        # State
        self.is_running = False
        self.is_paused = False
        self._workers: List[asyncio.Task] = []

        logger.info(f"NewsProcessorService initialized with {max_workers} workers")

    async def start(self):
        """Start the processing service."""
        if self.is_running:
            logger.warning("Processor service is already running")
            return

        self.is_running = True
        self.is_paused = False

        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

        logger.info(f"Started {self.max_workers} processing workers")

    async def stop(self):
        """Stop the processing service."""
        if not self.is_running:
            return

        logger.info("Stopping processor service...")
        self.is_running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info("Processor service stopped")

    async def pause(self):
        """Pause processing (finish current items but don't start new ones)."""
        self.is_paused = True
        logger.info("Processor service paused")

    async def resume(self):
        """Resume processing."""
        self.is_paused = False
        logger.info("Processor service resumed")

    async def process_article(
        self,
        article: NewsArticle,
        priority: int = 0,
        save_to_db: bool = True
    ) -> Optional[NewsArticle]:
        """
        Process a single article immediately (bypasses queue).

        Args:
            article: Article to process
            priority: Priority level (not used for immediate processing)
            save_to_db: Whether to save to database after processing

        Returns:
            Processed article or None if processing failed
        """
        try:
            logger.info(f"Processing article immediately: {article.id}")

            # Process the article
            processed_article = await self.processor.process_article(article)

            # Save to database if requested
            if save_to_db and processed_article.is_processed:
                await storage_service.save_article(processed_article)

            # Update statistics
            self.stats["total_processed"] += 1

            return processed_article

        except Exception as e:
            logger.error(f"Error processing article {article.id}: {str(e)}")
            self.stats["total_failed"] += 1
            return None

    async def queue_article(self, article: NewsArticle, priority: int = 0):
        """
        Add an article to the processing queue.

        Args:
            article: Article to queue
            priority: Priority level (higher = processed first)
        """
        item = ProcessingQueueItem(article, priority)
        self.queue.append(item)

        # Update max queue size stat
        if len(self.queue) > self.stats["queue_max_size"]:
            self.stats["queue_max_size"] = len(self.queue)

        logger.debug(f"Queued article {article.id} (queue size: {len(self.queue)})")

    async def queue_articles(self, articles: List[NewsArticle], priority: int = 0):
        """
        Add multiple articles to the processing queue.

        Args:
            articles: List of articles to queue
            priority: Priority level for all articles
        """
        for article in articles:
            await self.queue_article(article, priority)

        logger.info(f"Queued {len(articles)} articles for processing")

    async def process_batch(
        self,
        articles: List[NewsArticle],
        save_to_db: bool = True,
        use_queue: bool = False
    ) -> List[NewsArticle]:
        """
        Process a batch of articles.

        Args:
            articles: List of articles to process
            save_to_db: Whether to save to database after processing
            use_queue: If True, add to queue; if False, process immediately

        Returns:
            List of processed articles
        """
        if use_queue:
            # Add to queue for async processing
            await self.queue_articles(articles)
            return []

        # Process immediately
        processed_articles = []

        for article in articles:
            try:
                processed = await self.process_article(article, save_to_db=save_to_db)
                if processed:
                    processed_articles.append(processed)
            except Exception as e:
                logger.error(f"Error processing article {article.id}: {str(e)}")
                continue

        logger.info(f"Batch processed {len(processed_articles)}/{len(articles)} articles")
        return processed_articles

    async def process_collection(
        self,
        collection: NewsCollection,
        save_to_db: bool = True
    ) -> NewsCollection:
        """
        Process all articles in a collection.

        Args:
            collection: News collection to process
            save_to_db: Whether to save articles to database

        Returns:
            Collection with processed articles
        """
        logger.info(f"Processing collection {collection.id} with {len(collection.articles)} articles")

        processed_articles = await self.process_batch(
            collection.articles,
            save_to_db=save_to_db,
            use_queue=False
        )

        # Update collection
        collection.articles = processed_articles
        collection.processed_count = len([a for a in processed_articles if a.is_processed])

        # Save collection if requested
        if save_to_db:
            await storage_service.save_collection(collection)

        logger.info(f"Collection processed: {collection.processed_count}/{len(collection.articles)} articles")
        return collection

    async def _worker(self, worker_id: str):
        """
        Worker task that processes articles from the queue.

        Args:
            worker_id: Unique identifier for this worker
        """
        logger.info(f"Worker {worker_id} started")

        while self.is_running:
            try:
                # Wait if paused
                if self.is_paused:
                    await asyncio.sleep(1)
                    continue

                # Get next item from queue
                item = await self._get_next_item()

                if not item:
                    # No items in queue, wait a bit
                    await asyncio.sleep(0.5)
                    continue

                # Mark as processing
                item.started_at = datetime.now(timezone.utc)
                self.processing[item.article.id] = item

                logger.debug(f"Worker {worker_id} processing article {item.article.id}")

                # Process the article
                try:
                    processed_article = await self.processor.process_article(item.article)

                    # Save to database
                    if processed_article.is_processed:
                        await storage_service.save_article(processed_article)

                    # Mark as completed
                    item.completed_at = datetime.now(timezone.utc)
                    self.stats["total_processed"] += 1

                    # Update processing time statistics
                    if item.processing_time:
                        self.stats["total_processing_time"] += item.processing_time
                        self.stats["average_processing_time"] = (
                            self.stats["total_processing_time"] / self.stats["total_processed"]
                        )

                    logger.debug(
                        f"Worker {worker_id} completed article {item.article.id} "
                        f"in {item.processing_time:.2f}s"
                    )

                except Exception as e:
                    # Processing failed
                    item.error = str(e)
                    logger.error(f"Worker {worker_id} failed to process article {item.article.id}: {str(e)}")

                    # Retry if not exceeded max retries
                    if item.retry_count < self.max_retries:
                        item.retry_count += 1
                        self.stats["total_retries"] += 1
                        logger.info(f"Retrying article {item.article.id} (attempt {item.retry_count}/{self.max_retries})")
                        await self.queue_article(item.article, priority=item.priority)
                    else:
                        self.stats["total_failed"] += 1
                        logger.error(f"Article {item.article.id} failed after {self.max_retries} retries")

                finally:
                    # Remove from processing
                    self.processing.pop(item.article.id, None)

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    async def _get_next_item(self) -> Optional[ProcessingQueueItem]:
        """
        Get the next item from the queue (highest priority first).

        Returns:
            Next queue item or None if queue is empty
        """
        if not self.queue:
            return None

        # Sort by priority (higher first) and then by added time (FIFO)
        sorted_items = sorted(
            self.queue,
            key=lambda x: (-x.priority, x.added_at)
        )

        # Get the first item
        item = sorted_items[0]
        self.queue.remove(item)

        return item

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Dictionary containing processing stats
        """
        uptime = (datetime.now(timezone.utc) - self.stats["started_at"]).total_seconds()

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "uptime_seconds": uptime,
            "queue_size": len(self.queue),
            "processing_count": len(self.processing),
            "workers": len(self._workers),
            "max_workers": self.max_workers,
            "statistics": {
                **self.stats,
                "success_rate": (
                    self.stats["total_processed"] /
                    (self.stats["total_processed"] + self.stats["total_failed"])
                    if (self.stats["total_processed"] + self.stats["total_failed"]) > 0
                    else 0.0
                ),
                "articles_per_second": (
                    self.stats["total_processed"] / uptime
                    if uptime > 0 else 0.0
                )
            }
        }

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get detailed queue status.

        Returns:
            Dictionary with queue information
        """
        return {
            "total_queued": len(self.queue),
            "total_processing": len(self.processing),
            "queue_items": [
                {
                    "article_id": item.article.id,
                    "article_title": item.article.title[:50],
                    "priority": item.priority,
                    "retry_count": item.retry_count,
                    "wait_time": item.wait_time
                }
                for item in list(self.queue)[:10]  # Show first 10
            ],
            "processing_items": [
                {
                    "article_id": item.article.id,
                    "article_title": item.article.title[:50],
                    "processing_time": (datetime.now(timezone.utc) - item.started_at).total_seconds()
                    if item.started_at else 0
                }
                for item in self.processing.values()
            ]
        }

    async def clear_queue(self):
        """Clear all items from the queue (does not affect currently processing items)."""
        cleared_count = len(self.queue)
        self.queue.clear()
        logger.info(f"Cleared {cleared_count} items from processing queue")

    async def reprocess_failed_articles(self, limit: int = 100):
        """
        Reprocess articles that failed during previous processing attempts.

        Args:
            limit: Maximum number of failed articles to reprocess
        """
        # This would query the database for articles with is_processed=False
        # and add them back to the queue
        logger.info(f"Reprocessing up to {limit} failed articles")
        # Implementation depends on database query capabilities


# Global processor service instance
processor_service = NewsProcessorService(
    max_workers=5,
    max_retries=3
)
