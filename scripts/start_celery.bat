@echo off
REM Start Celery workers and beat scheduler for Windows

echo Starting Celery workers for NewsAgent...

REM Set Python path
set PYTHONPATH=%PYTHONPATH%;%CD%

REM Start workers in separate windows
start "Collection Worker" cmd /k celery -A src.celery_app:celery_app worker -Q collection -n collection_worker@%%h -c 2 -l info
start "Processing Worker" cmd /k celery -A src.celery_app:celery_app worker -Q processing -n processing_worker@%%h -c 4 -l info
start "Analysis Worker" cmd /k celery -A src.celery_app:celery_app worker -Q analysis -n analysis_worker@%%h -c 2 -l info
start "Storage Worker" cmd /k celery -A src.celery_app:celery_app worker -Q storage -n storage_worker@%%h -c 2 -l info
start "Monitoring Worker" cmd /k celery -A src.celery_app:celery_app worker -Q monitoring -n monitoring_worker@%%h -c 1 -l info
start "Default Worker" cmd /k celery -A src.celery_app:celery_app worker -Q default -n default_worker@%%h -c 2 -l info

REM Start beat scheduler
start "Celery Beat" cmd /k celery -A src.celery_app:celery_app beat -l info

echo All Celery workers started in separate windows!
echo To monitor workers, run: celery -A src.celery_app:celery_app flower
echo Flower will be available at http://localhost:5555
echo.
echo Close the worker windows to stop them.

pause
