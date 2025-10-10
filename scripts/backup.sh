#!/bin/bash
# Automated backup script for NewsAgent

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
LOG_FILE="/var/log/newsagent/backup.log"

# MongoDB configuration
MONGO_URI="${MONGODB_URI:-mongodb://localhost:27017/news_agent}"

# Redis configuration
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directories
mkdir -p "${BACKUP_DIR}"/{mongodb,redis,application}
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting backup process"

# 1. MongoDB Backup
log "Backing up MongoDB..."
mongodump --uri="$MONGO_URI" --out="${BACKUP_DIR}/mongodb/mongodb_backup_${TIMESTAMP}"
tar -czf "${BACKUP_DIR}/mongodb/mongodb_backup_${TIMESTAMP}.tar.gz" -C "${BACKUP_DIR}/mongodb" "mongodb_backup_${TIMESTAMP}"
rm -rf "${BACKUP_DIR}/mongodb/mongodb_backup_${TIMESTAMP}"
log "MongoDB backup completed"

# 2. Redis Backup
log "Backing up Redis..."
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE
sleep 5
cp /var/lib/redis/dump.rdb "${BACKUP_DIR}/redis/redis_backup_${TIMESTAMP}.rdb"
log "Redis backup completed"

# 3. Application Files Backup
log "Backing up application files..."
tar -czf "${BACKUP_DIR}/application/app_backup_${TIMESTAMP}.tar.gz" \
    -C /var/www/newsagent \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs' \
    .env src config scripts requirements.txt
log "Application backup completed"

# 4. Cleanup old backups
log "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -type f -mtime +${RETENTION_DAYS} -delete
log "Cleanup completed"

# 5. Backup summary
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Backup completed successfully. Total size: ${TOTAL_SIZE}"

exit 0
