"""
Celery application instance for asynchronous task processing.
"""

import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, worker_ready, worker_shutdown

from src.config.celery_config import celery_config

logger = logging.getLogger(__name__)


# Create Celery application
celery_app = Celery('newsagent')

# Load configuration
celery_app.config_from_object(celery_config)

# Auto-discover tasks in the tasks module
celery_app.autodiscover_tasks(['src.tasks'])


# Signal handlers
@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extra):
    """Handle task pre-run signal."""
    logger.info(f"Task {task.name}[{task_id}] starting with args={args}, kwargs={kwargs}")


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, **extra):
    """Handle task post-run signal."""
    logger.info(f"Task {task.name}[{task_id}] completed successfully")


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **extra):
    """Handle task failure signal."""
    logger.error(f"Task [{task_id}] failed with exception: {exception}")
    logger.error(f"Traceback: {traceback}")


@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handle worker ready signal."""
    logger.info(f"Worker {sender.hostname} is ready")


@worker_shutdown.connect
def worker_shutdown_handler(sender, **kwargs):
    """Handle worker shutdown signal."""
    logger.info(f"Worker {sender.hostname} is shutting down")


# Celery beat scheduler initialization
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks when Celery is configured."""
    logger.info("Celery beat scheduler configured with periodic tasks")


# Task base class with common functionality
class BaseTask(celery_app.Task):
    """Base task class with common functionality."""

    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Task {self.name}[{task_id}] retry attempt {self.request.retries}: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {self.name}[{task_id}] failed permanently: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {self.name}[{task_id}] succeeded")
        super().on_success(retval, task_id, args, kwargs)


# Update default task class
celery_app.Task = BaseTask


def get_celery_app():
    """Get the Celery application instance."""
    return celery_app


if __name__ == '__main__':
    # Run Celery worker
    celery_app.start()
