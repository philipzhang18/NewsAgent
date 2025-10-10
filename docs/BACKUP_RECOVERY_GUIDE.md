# Data Backup and Recovery Guide

## Overview

Comprehensive backup and recovery strategy for NewsAgent data, including MongoDB, Redis, and application files.

## Backup Strategy

### What Gets Backed Up

1. **MongoDB Database**: All news articles, collections, and metadata
2. **Redis Cache**: Cached data and Celery task results
3. **Application Files**: Configuration, source code, and scripts

### Backup Schedule

- **Frequency**: Daily at 2:00 AM
- **Retention**: 30 days
- **Method**: Automated via cron job

## Quick Start

### Automated Backup (Recommended)

```bash
# Run backup script
sudo /var/www/newsagent/scripts/backup.sh

# Check backup log
tail -f /var/log/newsagent/backup.log
```

### Manual Backup

```python
from src.services.backup_service import backup_service

# Full backup
result = backup_service.backup_all()

# Individual backups
mongodb_backup = backup_service.backup_mongodb(compress=True)
redis_backup = backup_service.backup_redis()
app_backup = backup_service.backup_application_files()
```

### Restore Data

```bash
# Restore all from backup
sudo ./scripts/restore.sh 20240101_120000 all

# Restore specific component
sudo ./scripts/restore.sh 20240101_120000 mongodb
```

## Setup

### 1. Configure Backup Directory

```bash
# Create backup directory
sudo mkdir -p /backup/{mongodb,redis,application}
sudo chown -R www-data:www-data /backup

# Set environment variable
export BACKUP_DIR=/backup
```

### 2. Install Cron Job

```bash
# Copy crontab file
sudo cp config/cron/backup-crontab /etc/cron.d/newsagent-backup

# Or edit crontab directly
sudo crontab -e

# Add line:
0 2 * * * /var/www/newsagent/scripts/backup.sh
```

### 3. Configure Retention

Edit `.env` or set environment variable:
```env
BACKUP_RETENTION_DAYS=30
```

## Backup Service API

### Backup Operations

```python
from src.services.backup_service import BackupService

# Initialize service
backup_service = BackupService(
    backup_dir='/backup',
    retention_days=30,
    mongodb_uri='mongodb://localhost:27017/news_agent'
)

# MongoDB backup
result = backup_service.backup_mongodb(compress=True)
print(f"Backup saved to: {result['path']}")
print(f"Size: {result['size_mb']} MB")

# Redis backup
result = backup_service.backup_redis()

# Application files backup
result = backup_service.backup_application_files(include_logs=False)

# Full backup
result = backup_service.backup_all()
print(f"Total size: {result['total_size_mb']} MB")
print(f"Success: {result['success_count']}/{len(result['backups'])}")
```

### Restore Operations

```python
# Restore MongoDB
success = backup_service.restore_mongodb('/backup/mongodb/mongodb_backup_20240101.tar.gz')

# Restore Redis
success = backup_service.restore_redis('/backup/redis/redis_backup_20240101.rdb')
```

### List Backups

```python
backups = backup_service.list_backups()

for backup_type, backup_list in backups.items():
    print(f"\n{backup_type.upper()} Backups:")
    for backup in backup_list:
        print(f"  - {backup['name']} ({backup['size_mb']} MB)")
```

### Cleanup Old Backups

```python
result = backup_service.cleanup_old_backups()
print(f"Removed {result['removed_count']} backups ({result['removed_size_mb']} MB)")
```

## Backup Scripts

### backup.sh

Automated backup script that:
- Backs up MongoDB with compression
- Backs up Redis RDB file
- Backs up application files
- Cleans up old backups
- Logs all operations

**Usage:**
```bash
sudo ./scripts/backup.sh
```

### restore.sh

Restore script that:
- Restores MongoDB from backup
- Restores Redis from backup
- Restores application files
- Manages service restarts

**Usage:**
```bash
# Restore all
sudo ./scripts/restore.sh 20240101_120000 all

# Restore specific component
sudo ./scripts/restore.sh 20240101_120000 mongodb
sudo ./scripts/restore.sh 20240101_120000 redis
sudo ./scripts/restore.sh 20240101_120000 application
```

## Testing Backups

### Verify Backup Integrity

```bash
# Test MongoDB backup
mongodump --archive=test.archive --uri="mongodb://localhost:27017/news_agent"
mongorestore --archive=test.archive --nsFrom='news_agent.*' --nsTo='test_db.*'

# Test Redis backup
redis-cli --rdb /tmp/test.rdb

# Test application backup
tar -tzf /backup/application/app_backup_latest.tar.gz
```

### Test Restore Process

```bash
# Create test environment
# Restore to test database/instance
# Verify data integrity
```

## Monitoring

### Check Backup Status

```bash
# View backup log
tail -f /var/log/newsagent/backup.log

# Check backup sizes
du -sh /backup/*

# List recent backups
ls -lht /backup/mongodb/ | head
ls -lht /backup/redis/ | head
```

### Backup Alerts

Configure monitoring to alert on:
- Backup failures
- Backup size anomalies
- Missing backups
- Storage space issues

## Storage Recommendations

### Local Storage

- **Location**: `/backup` on separate disk/partition
- **Capacity**: 5-10x daily backup size
- **RAID**: RAID 1 or RAID 10 for redundancy

### Remote Storage

Sync backups to remote storage:

```bash
# AWS S3
aws s3 sync /backup s3://newsagent-backups/

# rsync to remote server
rsync -avz /backup/ backup-server:/backups/newsagent/

# Google Cloud Storage
gsutil -m rsync -r /backup gs://newsagent-backups/
```

## Disaster Recovery

### Recovery Time Objective (RTO)

- **MongoDB**: 10-15 minutes
- **Redis**: 2-5 minutes
- **Application**: 5-10 minutes
- **Total**: ~30 minutes

### Recovery Point Objective (RPO)

- **Maximum data loss**: 24 hours (daily backups)
- **Improve RPO**: Increase backup frequency

### Full System Recovery

```bash
# 1. Provision new server
# 2. Install dependencies
sudo apt-get install mongodb redis-server

# 3. Restore MongoDB
sudo ./scripts/restore.sh 20240101_120000 mongodb

# 4. Restore Redis
sudo ./scripts/restore.sh 20240101_120000 redis

# 5. Restore application
sudo ./scripts/restore.sh 20240101_120000 application

# 6. Verify services
sudo systemctl status newsagent mongodb redis-server
```

## Best Practices

1. **Test Restores Regularly**: Monthly restore tests
2. **Monitor Backup Jobs**: Set up alerts for failures
3. **Store Offsite**: Keep copies in different location
4. **Encrypt Backups**: For sensitive data
5. **Document Procedures**: Keep recovery docs updated
6. **Verify Integrity**: Check backup files regularly
7. **Automate Everything**: Use scripts and cron
8. **Monitor Storage**: Ensure sufficient space

## Troubleshooting

### Backup Fails

```bash
# Check permissions
ls -la /backup

# Check disk space
df -h /backup

# Check logs
tail -f /var/log/newsagent/backup.log

# Test MongoDB connection
mongosh "$MONGODB_URI"

# Test Redis connection
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
```

### Restore Fails

```bash
# Verify backup file exists
ls -l /backup/mongodb/mongodb_backup_*.tar.gz

# Check file integrity
tar -tzf backup.tar.gz > /dev/null

# Check services
systemctl status mongodb redis-server

# Check logs
journalctl -u mongodb -n 50
journalctl -u redis-server -n 50
```

## Docker Backup

For Docker deployments:

```bash
# Backup MongoDB container
docker exec newsagent-mongodb mongodump --archive=/backup/mongodb.archive

# Backup volumes
docker run --rm --volumes-from newsagent-mongodb -v /backup:/backup ubuntu tar czf /backup/mongodb-volume.tar.gz /data/db

# Restore
docker run --rm --volumes-from newsagent-mongodb -v /backup:/backup ubuntu tar xzf /backup/mongodb-volume.tar.gz -C /
```

## References

- [MongoDB Backup Methods](https://docs.mongodb.com/manual/core/backups/)
- [Redis Persistence](https://redis.io/topics/persistence)
- [Disaster Recovery Best Practices](https://www.ibm.com/cloud/learn/disaster-recovery)
