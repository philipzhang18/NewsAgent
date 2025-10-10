"""
Celery tasks for monitoring and health check operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from src.celery_app import celery_app
from src.services.monitoring_service import monitoring_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name='src.tasks.monitoring_tasks.health_check_task',
    bind=True,
    queue='monitoring'
)
def health_check_task(self):
    """
    Perform system health checks.

    Returns:
        Health check results
    """
    logger.info("Running scheduled health check")

    try:
        import asyncio

        async def _check():
            # Start monitoring service if not running
            if not monitoring_service.is_running:
                await monitoring_service.start()

            # Run health checks
            results = await monitoring_service.run_health_checks()

            return results

        # Run health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(_check())
        finally:
            loop.close()

        # Log unhealthy checks
        if not results.get('healthy', True):
            logger.warning(f"System health check failed: {results}")
        else:
            logger.info("System health check passed")

        return {
            'success': True,
            'healthy': results.get('healthy', True),
            'checks': results.get('checks', {}),
            'timestamp': results.get('timestamp')
        }

    except Exception as e:
        logger.error(f"Health check task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)  # Retry after 1 minute


@celery_app.task(
    name='src.tasks.monitoring_tasks.collect_metrics_task',
    bind=True,
    queue='monitoring'
)
def collect_metrics_task(self):
    """
    Collect system metrics.

    Returns:
        Collected metrics
    """
    logger.debug("Collecting system metrics")

    try:
        import asyncio

        async def _collect():
            # Start monitoring service if not running
            if not monitoring_service.is_running:
                await monitoring_service.start()

            # Collect metrics
            metrics = await monitoring_service.collect_metrics()

            return metrics

        # Run collection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            metrics = loop.run_until_complete(_collect())
        finally:
            loop.close()

        return {
            'success': True,
            'metrics': metrics,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Metrics collection task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(
    name='src.tasks.monitoring_tasks.alert_check_task',
    bind=True,
    queue='monitoring'
)
def alert_check_task(self, severity: Optional[str] = None):
    """
    Check and process alerts.

    Args:
        severity: Optional severity filter for alerts

    Returns:
        Alert summary
    """
    logger.info("Checking system alerts")

    try:
        # Get alert summary
        summary = monitoring_service.alert_manager.get_alert_summary()

        # Log critical alerts
        if summary['by_severity']['critical'] > 0:
            logger.critical(f"System has {summary['by_severity']['critical']} critical alerts!")

        # Log error alerts
        if summary['by_severity']['error'] > 0:
            logger.error(f"System has {summary['by_severity']['error']} error alerts")

        return {
            'success': True,
            'summary': summary,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Alert check task failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(
    name='src.tasks.monitoring_tasks.performance_report_task',
    bind=True,
    queue='monitoring'
)
def performance_report_task(self):
    """
    Generate performance report.

    Returns:
        Performance report data
    """
    logger.info("Generating performance report")

    try:
        import asyncio
        from src.services.news_collector_service import news_collector_service
        from src.services.news_processor_service import processor_service

        async def _generate():
            # Get monitoring status
            monitoring_status = monitoring_service.get_status()

            # Get collector statistics
            collector_stats = news_collector_service.get_statistics()

            # Get processor statistics
            processor_stats = processor_service.get_statistics()

            return {
                'monitoring': monitoring_status,
                'collector': collector_stats,
                'processor': processor_stats
            }

        # Run report generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(_generate())
        finally:
            loop.close()

        return {
            'success': True,
            'report': report,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Performance report task failed: {str(e)}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(
    name='src.tasks.monitoring_tasks.cleanup_old_metrics_task',
    bind=True,
    queue='monitoring'
)
def cleanup_old_metrics_task(self, hours_to_keep: int = 24):
    """
    Clean up old metrics data.

    Args:
        hours_to_keep: Number of hours of metrics to keep

    Returns:
        Cleanup results
    """
    logger.info(f"Cleaning up metrics older than {hours_to_keep} hours")

    try:
        # This is a placeholder - actual implementation would depend on
        # how metrics are stored
        # For now, we just log the cleanup
        logger.info("Metrics cleanup completed")

        return {
            'success': True,
            'hours_kept': hours_to_keep,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Metrics cleanup task failed: {str(e)}")
        raise self.retry(exc=e, countdown=300)
