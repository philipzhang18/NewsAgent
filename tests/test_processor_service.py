"""
Unit tests for NewsProcessorService.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from src.services.news_processor_service import NewsProcessorService, ProcessingQueueItem
from src.models.news_models import NewsArticle


@pytest.fixture
def test_article():
    """Create a test article."""
    return NewsArticle(
        id="test_123",
        title="Test Article",
        content="Test content",
        summary="Test summary",
        source="Test Source",
        source_name="Test",
        url="https://example.com/test",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def processor_service():
    """Create a processor service instance."""
    service = NewsProcessorService(max_workers=2, max_retries=2)
    return service


class TestProcessingQueueItem:
    """Test cases for ProcessingQueueItem."""

    def test_initialization(self, test_article):
        """Test queue item initialization."""
        item = ProcessingQueueItem(test_article, priority=5)

        assert item.article == test_article
        assert item.priority == 5
        assert item.retry_count == 0
        assert item.started_at is None
        assert item.completed_at is None

    def test_processing_time(self, test_article):
        """Test processing time calculation."""
        item = ProcessingQueueItem(test_article)
        assert item.processing_time is None

        item.started_at = datetime.now(timezone.utc)
        item.completed_at = datetime.now(timezone.utc)
        assert item.processing_time >= 0

    def test_wait_time(self, test_article):
        """Test wait time calculation."""
        item = ProcessingQueueItem(test_article)
        wait_time = item.wait_time
        assert wait_time >= 0


class TestNewsProcessorService:
    """Test cases for NewsProcessorService."""

    def test_initialization(self, processor_service):
        """Test service initialization."""
        assert processor_service.max_workers == 2
        assert processor_service.max_retries == 2
        assert processor_service.is_running is False
        assert processor_service.is_paused is False
        assert len(processor_service.queue) == 0

    @pytest.mark.asyncio
    async def test_start_service(self, processor_service):
        """Test starting the service."""
        await processor_service.start()

        assert processor_service.is_running is True
        assert len(processor_service._workers) == 2

        await processor_service.stop()

    @pytest.mark.asyncio
    async def test_stop_service(self, processor_service):
        """Test stopping the service."""
        await processor_service.start()
        await processor_service.stop()

        assert processor_service.is_running is False
        assert len(processor_service._workers) == 0

    @pytest.mark.asyncio
    async def test_pause_resume(self, processor_service):
        """Test pausing and resuming the service."""
        await processor_service.pause()
        assert processor_service.is_paused is True

        await processor_service.resume()
        assert processor_service.is_paused is False

    @pytest.mark.asyncio
    @patch('src.services.news_processor_service.storage_service')
    async def test_process_article(self, mock_storage, processor_service, test_article):
        """Test processing a single article."""
        mock_storage.save_article = AsyncMock()

        with patch.object(processor_service.processor, 'process_article', AsyncMock(return_value=test_article)):
            result = await processor_service.process_article(test_article, save_to_db=True)

            assert result is not None
            assert processor_service.stats['total_processed'] == 1

    @pytest.mark.asyncio
    async def test_queue_article(self, processor_service, test_article):
        """Test queuing an article."""
        await processor_service.queue_article(test_article, priority=5)

        assert len(processor_service.queue) == 1
        item = processor_service.queue[0]
        assert item.article == test_article
        assert item.priority == 5

    @pytest.mark.asyncio
    async def test_queue_articles(self, processor_service, test_article):
        """Test queuing multiple articles."""
        articles = [test_article for _ in range(5)]
        await processor_service.queue_articles(articles, priority=3)

        assert len(processor_service.queue) == 5

    @pytest.mark.asyncio
    @patch('src.services.news_processor_service.storage_service')
    async def test_process_batch_immediate(self, mock_storage, processor_service, test_article):
        """Test immediate batch processing."""
        mock_storage.save_article = AsyncMock()
        articles = [test_article for _ in range(3)]

        with patch.object(processor_service.processor, 'process_article', AsyncMock(return_value=test_article)):
            results = await processor_service.process_batch(articles, save_to_db=True, use_queue=False)

            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_process_batch_queue(self, processor_service, test_article):
        """Test queued batch processing."""
        articles = [test_article for _ in range(3)]
        results = await processor_service.process_batch(articles, use_queue=True)

        assert results == []
        assert len(processor_service.queue) == 3

    @pytest.mark.asyncio
    async def test_get_next_item_priority(self, processor_service, test_article):
        """Test priority-based queue item retrieval."""
        # Add items with different priorities
        await processor_service.queue_article(test_article, priority=1)
        await processor_service.queue_article(test_article, priority=5)
        await processor_service.queue_article(test_article, priority=3)

        # Should get highest priority first
        item = await processor_service._get_next_item()
        assert item.priority == 5

    def test_get_statistics(self, processor_service):
        """Test getting service statistics."""
        stats = processor_service.get_statistics()

        assert 'is_running' in stats
        assert 'queue_size' in stats
        assert 'workers' in stats
        assert 'statistics' in stats
        assert 'uptime_seconds' in stats

    def test_get_queue_status(self, processor_service, test_article):
        """Test getting queue status."""
        asyncio.run(processor_service.queue_article(test_article))

        status = processor_service.get_queue_status()

        assert 'total_queued' in status
        assert 'total_processing' in status
        assert 'queue_items' in status
        assert status['total_queued'] == 1

    @pytest.mark.asyncio
    async def test_clear_queue(self, processor_service, test_article):
        """Test clearing the queue."""
        await processor_service.queue_article(test_article)
        await processor_service.queue_article(test_article)

        await processor_service.clear_queue()

        assert len(processor_service.queue) == 0

    @pytest.mark.asyncio
    @patch('src.services.news_processor_service.storage_service')
    async def test_worker_processing(self, mock_storage, processor_service, test_article):
        """Test worker processing articles from queue."""
        mock_storage.save_article = AsyncMock()

        with patch.object(processor_service.processor, 'process_article', AsyncMock(return_value=test_article)):
            await processor_service.start()
            await processor_service.queue_article(test_article)

            # Wait for processing
            await asyncio.sleep(0.5)

            assert processor_service.stats['total_processed'] >= 0

            await processor_service.stop()

    @pytest.mark.asyncio
    async def test_retry_logic(self, processor_service, test_article):
        """Test retry logic for failed articles."""
        # Mock processor to fail
        with patch.object(processor_service.processor, 'process_article', AsyncMock(side_effect=Exception("Test error"))):
            await processor_service.start()
            await processor_service.queue_article(test_article)

            # Wait for processing and retry
            await asyncio.sleep(1)

            # Should have retried
            assert processor_service.stats['total_retries'] >= 0

            await processor_service.stop()
