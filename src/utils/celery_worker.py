"""
Celery worker and beat management utilities.
"""

import os
import sys
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CeleryWorkerManager:
    """Manage Celery workers and beat scheduler."""

    def __init__(self, app_name: str = 'src.celery_app:celery_app'):
        """
        Initialize worker manager.

        Args:
            app_name: Celery application module path
        """
        self.app_name = app_name
        self.worker_processes = []
        self.beat_process = None

    def start_worker(
        self,
        queue: str = 'default',
        concurrency: Optional[int] = None,
        loglevel: str = 'info',
        name: Optional[str] = None
    ) -> subprocess.Popen:
        """
        Start a Celery worker.

        Args:
            queue: Queue name for the worker
            concurrency: Number of concurrent workers
            loglevel: Logging level
            name: Worker name

        Returns:
            Worker process
        """
        worker_name = name or f'worker_{queue}'
        concurrency_arg = f'-c {concurrency}' if concurrency else ''

        cmd = (
            f'celery -A {self.app_name} worker '
            f'-Q {queue} '
            f'-n {worker_name}@%h '
            f'{concurrency_arg} '
            f'-l {loglevel}'
        )

        logger.info(f"Starting worker: {cmd}")

        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        self.worker_processes.append(process)
        return process

    def start_beat(self, loglevel: str = 'info') -> subprocess.Popen:
        """
        Start Celery beat scheduler.

        Args:
            loglevel: Logging level

        Returns:
            Beat process
        """
        cmd = f'celery -A {self.app_name} beat -l {loglevel}'

        logger.info(f"Starting beat scheduler: {cmd}")

        self.beat_process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        return self.beat_process

    def start_flower(self, port: int = 5555, address: str = '0.0.0.0') -> subprocess.Popen:
        """
        Start Flower monitoring web UI.

        Args:
            port: Port for Flower web UI
            address: Address to bind to

        Returns:
            Flower process
        """
        cmd = f'celery -A {self.app_name} flower --port={port} --address={address}'

        logger.info(f"Starting Flower: {cmd}")

        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        return process

    def stop_all(self):
        """Stop all workers and beat scheduler."""
        logger.info("Stopping all Celery processes")

        # Stop workers
        for process in self.worker_processes:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception as e:
                logger.error(f"Error stopping worker: {e}")
                process.kill()

        # Stop beat
        if self.beat_process:
            try:
                self.beat_process.terminate()
                self.beat_process.wait(timeout=10)
            except Exception as e:
                logger.error(f"Error stopping beat: {e}")
                self.beat_process.kill()

        self.worker_processes = []
        self.beat_process = None

        logger.info("All Celery processes stopped")


def start_default_workers():
    """Start default worker configuration."""
    manager = CeleryWorkerManager()

    # Start workers for different queues
    manager.start_worker(queue='collection', concurrency=2, name='collection_worker')
    manager.start_worker(queue='processing', concurrency=4, name='processing_worker')
    manager.start_worker(queue='analysis', concurrency=2, name='analysis_worker')
    manager.start_worker(queue='default', concurrency=2, name='default_worker')
    manager.start_worker(queue='monitoring', concurrency=1, name='monitoring_worker')

    # Start beat scheduler
    manager.start_beat()

    logger.info("All workers started successfully")

    return manager


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'worker':
            # Start single worker
            queue = sys.argv[2] if len(sys.argv) > 2 else 'default'
            os.system(f'celery -A src.celery_app:celery_app worker -Q {queue} -l info')

        elif command == 'beat':
            # Start beat scheduler
            os.system('celery -A src.celery_app:celery_app beat -l info')

        elif command == 'flower':
            # Start flower monitoring
            port = sys.argv[2] if len(sys.argv) > 2 else '5555'
            os.system(f'celery -A src.celery_app:celery_app flower --port={port}')

        elif command == 'all':
            # Start all workers and beat
            manager = start_default_workers()
            print("Press Ctrl+C to stop all workers")
            try:
                # Keep running
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                manager.stop_all()

        else:
            print(f"Unknown command: {command}")
            print("Usage: python -m src.utils.celery_worker [worker|beat|flower|all] [args]")

    else:
        print("Celery Worker Manager")
        print("Usage:")
        print("  python -m src.utils.celery_worker worker [queue]  - Start worker")
        print("  python -m src.utils.celery_worker beat            - Start beat scheduler")
        print("  python -m src.utils.celery_worker flower [port]   - Start flower monitoring")
        print("  python -m src.utils.celery_worker all             - Start all workers and beat")
