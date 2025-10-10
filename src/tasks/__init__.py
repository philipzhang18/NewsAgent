"""
Task definitions package.
"""

from src.tasks.news_tasks import (
    collect_news_task,
    process_article_task,
    analyze_batch_task,
    store_article_task,
    cleanup_old_data_task
)

from src.tasks.monitoring_tasks import (
    health_check_task,
    collect_metrics_task
)

__all__ = [
    'collect_news_task',
    'process_article_task',
    'analyze_batch_task',
    'store_article_task',
    'cleanup_old_data_task',
    'health_check_task',
    'collect_metrics_task'
]
