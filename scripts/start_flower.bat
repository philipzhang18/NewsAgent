@echo off
REM Start Celery Flower monitoring interface

echo Starting Celery Flower monitoring...

celery -A src.celery_app:celery_app flower --port=5555 --address=0.0.0.0

echo Flower is running at http://localhost:5555
pause
