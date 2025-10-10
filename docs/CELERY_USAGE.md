# Celery Task Queue Documentation

## Overview

The NewsAgent application uses Celery for asynchronous task processing. This allows long-running tasks like news collection, article processing, and analysis to run in the background without blocking the web application.

## Architecture

### Components

1. **Celery Workers**: Execute tasks from queues
2. **Celery Beat**: Scheduler for periodic tasks
3. **Redis**: Message broker and result backend
4. **Flower**: Web-based monitoring UI (optional)

### Task Queues

- **collection**: News collection tasks (priority: 7)
- **processing**: Article processing tasks (priority: 8)
- **analysis**: Batch analysis tasks (priority: 6)
- **storage**: Database storage tasks (priority: 5)
- **monitoring**: Health checks and metrics (priority: 3)
- **default**: General tasks (priority: 5)

## Configuration

### Environment Variables

```bash
# Celery broker (Redis)
CELERY_BROKER_URL=redis://localhost:6379/0

# Result backend
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Worker concurrency
CELERY_WORKER_CONCURRENCY=4

# Flask environment
FLASK_ENV=development  # or production
```

### Configuration Files

- `src/config/celery_config.py`: Main Celery configuration
- `src/celery_app.py`: Celery application instance

## Available Tasks

### News Tasks (`src/tasks/news_tasks.py`)

#### collect_news_task
Collects news from configured sources.
```python
from src.tasks.news_tasks import collect_news_task

# Collect from all sources
result = collect_news_task.delay()

# Collect from specific sources
result = collect_news_task.delay(source_ids=['newsapi', 'rss_tech'])
```

#### process_article_task
Processes a single news article.
```python
from src.tasks.news_tasks import process_article_task

article_data = {...}  # Article dictionary
result = process_article_task.delay(article_data)
```

#### analyze_batch_task
Analyzes a batch of articles.
```python
from src.tasks.news_tasks import analyze_batch_task

article_ids = ['id1', 'id2', 'id3']
result = analyze_batch_task.delay(article_ids)
```

#### cleanup_old_data_task
Cleans up old articles (scheduled daily).
```python
from src.tasks.news_tasks import cleanup_old_data_task

# Keep last 30 days
result = cleanup_old_data_task.delay(days_to_keep=30)
```

### Monitoring Tasks (`src/tasks/monitoring_tasks.py`)

#### health_check_task
Performs system health checks (scheduled every 5 minutes).
```python
from src.tasks.monitoring_tasks import health_check_task

result = health_check_task.delay()
```

#### collect_metrics_task
Collects system metrics (scheduled every minute).
```python
from src.tasks.monitoring_tasks import collect_metrics_task

result = collect_metrics_task.delay()
```

## Periodic Tasks Schedule

Configured in `src/config/celery_config.py`:

| Task | Schedule | Queue |
|------|----------|-------|
| collect_news_task | Every 30 minutes | collection |
| health_check_task | Every 5 minutes | monitoring |
| collect_metrics_task | Every 1 minute | monitoring |
| cleanup_old_data_task | Daily at 2 AM | default |

## Running Celery

### Start All Workers (Windows)

```bash
# Start all workers and beat
.\scripts\start_celery.bat

# Start Flower monitoring
.\scripts\start_flower.bat
```

### Start All Workers (Linux/Mac)

```bash
# Make script executable
chmod +x scripts/start_celery.sh

# Start all workers and beat
./scripts/start_celery.sh

# Start Flower monitoring
celery -A src.celery_app:celery_app flower
```

### Start Individual Components

```bash
# Single worker
celery -A src.celery_app:celery_app worker -Q collection -l info

# Beat scheduler
celery -A src.celery_app:celery_app beat -l info

# Flower monitoring
celery -A src.celery_app:celery_app flower --port=5555
```

## Using the Worker Manager

The `src/utils/celery_worker.py` module provides utilities for managing workers:

```python
from src.utils.celery_worker import CeleryWorkerManager, start_default_workers

# Start all default workers
manager = start_default_workers()

# Or manually start specific workers
manager = CeleryWorkerManager()
manager.start_worker(queue='collection', concurrency=2)
manager.start_worker(queue='processing', concurrency=4)
manager.start_beat()
manager.start_flower(port=5555)

# Stop all workers
manager.stop_all()
```

## Monitoring with Flower

Flower provides a web interface to monitor Celery workers and tasks.

1. Start Flower:
   ```bash
   celery -A src.celery_app:celery_app flower
   ```

2. Access the web interface:
   ```
   http://localhost:5555
   ```

Features:
- Real-time worker monitoring
- Task history and statistics
- Task detail inspection
- Worker pool management
- Rate limit configuration

## Task Result Handling

```python
from src.tasks.news_tasks import collect_news_task

# Submit task
result = collect_news_task.delay()

# Check if ready
if result.ready():
    # Get result (blocking)
    data = result.get(timeout=10)
    print(data)

# Non-blocking check
status = result.status  # PENDING, STARTED, SUCCESS, FAILURE
task_id = result.id
```

## Error Handling and Retries

All tasks inherit from `BaseTask` with automatic retry logic:

- **Max retries**: 3
- **Retry backoff**: Exponential with jitter
- **Max backoff**: 600 seconds (10 minutes)

Tasks automatically retry on:
- Connection errors
- Temporary failures
- Rate limit errors

## Best Practices

1. **Queue Selection**: Use appropriate queues for different task types
2. **Task Idempotency**: Design tasks to be safely retried
3. **Result Expiration**: Results expire after 1 hour by default
4. **Worker Monitoring**: Use Flower or logs to monitor worker health
5. **Resource Management**: Adjust concurrency based on available resources
6. **Rate Limiting**: Configure task rate limits to prevent API overload
7. **Error Handling**: Let tasks fail gracefully and retry

## Troubleshooting

### Worker Not Starting

```bash
# Check Redis connection
redis-cli ping

# Check Celery configuration
celery -A src.celery_app:celery_app inspect active_queues
```

### Tasks Not Executing

```bash
# Check worker status
celery -A src.celery_app:celery_app inspect active

# Check registered tasks
celery -A src.celery_app:celery_app inspect registered
```

### High Task Failure Rate

1. Check worker logs
2. Verify API credentials and rate limits
3. Check database connections
4. Monitor system resources

## Production Deployment

For production environments:

1. Use `ProductionCeleryConfig` in `celery_config.py`
2. Configure Redis Sentinel for high availability
3. Use supervisor or systemd for process management
4. Set up proper logging and monitoring
5. Configure firewall rules for Redis access
6. Use SSL/TLS for Redis connections

Example systemd service file:

```ini
[Unit]
Description=Celery Worker for NewsAgent
After=network.target redis.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/newsagent
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
ExecStart=/path/to/venv/bin/celery -A src.celery_app:celery_app worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
