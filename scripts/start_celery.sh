#!/bin/bash
# Start Celery workers and beat scheduler

echo "Starting Celery workers for NewsAgent..."

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start collection worker
celery -A src.celery_app:celery_app worker -Q collection -n collection_worker@%h -c 2 -l info &

# Start processing worker
celery -A src.celery_app:celery_app worker -Q processing -n processing_worker@%h -c 4 -l info &

# Start analysis worker
celery -A src.celery_app:celery_app worker -Q analysis -n analysis_worker@%h -c 2 -l info &

# Start storage worker
celery -A src.celery_app:celery_app worker -Q storage -n storage_worker@%h -c 2 -l info &

# Start monitoring worker
celery -A src.celery_app:celery_app worker -Q monitoring -n monitoring_worker@%h -c 1 -l info &

# Start default worker
celery -A src.celery_app:celery_app worker -Q default -n default_worker@%h -c 2 -l info &

# Start beat scheduler
celery -A src.celery_app:celery_app beat -l info &

echo "All Celery workers started!"
echo "To monitor workers, run: celery -A src.celery_app:celery_app flower"
echo "Flower will be available at http://localhost:5555"
echo ""
echo "Press Ctrl+C to stop all workers"

# Wait for all background jobs
wait
