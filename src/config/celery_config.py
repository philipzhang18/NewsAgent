"""
Celery configuration for asynchronous task processing.
"""

import os
from datetime import timedelta
from kombu import Queue, Exchange


class CeleryConfig:
    """Celery configuration class."""

    # Broker settings (Redis)
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

    # Task settings
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'UTC'
    enable_utc = True

    # Task result settings
    result_expires = 3600  # 1 hour
    result_persistent = True

    # Task execution settings
    task_acks_late = True  # Tasks are acknowledged after execution
    task_reject_on_worker_lost = True  # Reject task if worker dies
    task_track_started = True  # Track when task starts
    worker_prefetch_multiplier = 1  # Fetch one task at a time
    worker_max_tasks_per_child = 1000  # Restart worker after N tasks

    # Task time limits (in seconds)
    task_soft_time_limit = 300  # 5 minutes soft limit
    task_time_limit = 600  # 10 minutes hard limit

    # Queue configuration
    task_default_queue = 'default'
    task_default_exchange = 'tasks'
    task_default_routing_key = 'default'

    # Define queues with priorities
    task_queues = (
        Queue('default', Exchange('tasks'), routing_key='default', priority=5),
        Queue('collection', Exchange('tasks'), routing_key='collection', priority=7),
        Queue('processing', Exchange('tasks'), routing_key='processing', priority=8),
        Queue('analysis', Exchange('tasks'), routing_key='analysis', priority=6),
        Queue('storage', Exchange('tasks'), routing_key='storage', priority=5),
        Queue('monitoring', Exchange('tasks'), routing_key='monitoring', priority=3),
    )

    # Task routing
    task_routes = {
        'src.tasks.news_tasks.collect_news_task': {
            'queue': 'collection',
            'routing_key': 'collection',
        },
        'src.tasks.news_tasks.process_article_task': {
            'queue': 'processing',
            'routing_key': 'processing',
        },
        'src.tasks.news_tasks.analyze_batch_task': {
            'queue': 'analysis',
            'routing_key': 'analysis',
        },
        'src.tasks.news_tasks.store_article_task': {
            'queue': 'storage',
            'routing_key': 'storage',
        },
        'src.tasks.news_tasks.cleanup_old_data_task': {
            'queue': 'default',
            'routing_key': 'default',
        },
        'src.tasks.monitoring_tasks.health_check_task': {
            'queue': 'monitoring',
            'routing_key': 'monitoring',
        },
        'src.tasks.monitoring_tasks.collect_metrics_task': {
            'queue': 'monitoring',
            'routing_key': 'monitoring',
        },
    }

    # Beat schedule (periodic tasks)
    beat_schedule = {
        # Collect news every 30 minutes
        'collect-news-every-30-minutes': {
            'task': 'src.tasks.news_tasks.collect_news_task',
            'schedule': timedelta(minutes=30),
            'options': {'queue': 'collection'}
        },
        # Health check every 5 minutes
        'health-check-every-5-minutes': {
            'task': 'src.tasks.monitoring_tasks.health_check_task',
            'schedule': timedelta(minutes=5),
            'options': {'queue': 'monitoring'}
        },
        # Collect metrics every minute
        'collect-metrics-every-minute': {
            'task': 'src.tasks.monitoring_tasks.collect_metrics_task',
            'schedule': timedelta(minutes=1),
            'options': {'queue': 'monitoring'}
        },
        # Cleanup old data daily at 2 AM
        'cleanup-old-data-daily': {
            'task': 'src.tasks.news_tasks.cleanup_old_data_task',
            'schedule': timedelta(days=1),
            'options': {'queue': 'default'}
        },
    }

    # Worker settings
    worker_send_task_events = True
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

    # Concurrency settings
    worker_concurrency = os.getenv('CELERY_WORKER_CONCURRENCY', 4)
    worker_pool = 'prefork'  # Use multiprocessing

    # Redis connection pool settings
    broker_transport_options = {
        'visibility_timeout': 3600,  # 1 hour
        'max_connections': 20,
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
    }

    # Task annotations
    task_annotations = {
        '*': {
            'rate_limit': '100/m',  # 100 tasks per minute per worker
        },
        'src.tasks.news_tasks.collect_news_task': {
            'rate_limit': '20/m',  # 20 collection tasks per minute
        },
        'src.tasks.news_tasks.process_article_task': {
            'rate_limit': '50/m',  # 50 processing tasks per minute
        },
    }

    # Error handling
    task_ignore_result = False
    task_store_errors_even_if_ignored = True

    # Logging
    worker_hijack_root_logger = False
    worker_redirect_stdouts = True
    worker_redirect_stdouts_level = 'INFO'


# Environment-specific configurations
class DevelopmentCeleryConfig(CeleryConfig):
    """Development environment Celery configuration."""
    worker_log_level = 'DEBUG'
    beat_schedule = {
        # More frequent in development
        'collect-news-every-5-minutes': {
            'task': 'src.tasks.news_tasks.collect_news_task',
            'schedule': timedelta(minutes=5),
        },
    }


class ProductionCeleryConfig(CeleryConfig):
    """Production environment Celery configuration."""
    worker_log_level = 'INFO'
    broker_connection_retry_on_startup = True
    broker_connection_retry = True
    broker_connection_max_retries = 10
    result_backend_transport_options = {
        'master_name': 'mymaster',  # For Redis Sentinel
    }


# Select configuration based on environment
def get_celery_config():
    """Get Celery configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development')

    if env == 'production':
        return ProductionCeleryConfig
    else:
        return DevelopmentCeleryConfig


celery_config = get_celery_config()
