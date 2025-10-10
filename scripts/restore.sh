#!/bin/bash
# Restore script for NewsAgent

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup}"
LOG_FILE="/var/log/newsagent/restore.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check if backup path provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_timestamp> [mongodb|redis|application|all]"
    echo "Example: $0 20240101_120000 all"
    exit 1
fi

TIMESTAMP="$1"
RESTORE_TYPE="${2:-all}"

log "Starting restore process for timestamp: ${TIMESTAMP}"

# Restore MongoDB
restore_mongodb() {
    log "Restoring MongoDB..."
    MONGODB_BACKUP="${BACKUP_DIR}/mongodb/mongodb_backup_${TIMESTAMP}.tar.gz"

    if [ ! -f "$MONGODB_BACKUP" ]; then
        log "ERROR: MongoDB backup not found: $MONGODB_BACKUP"
        return 1
    fi

    # Extract backup
    TEMP_DIR=$(mktemp -d)
    tar -xzf "$MONGODB_BACKUP" -C "$TEMP_DIR"

    # Restore
    mongorestore --uri="$MONGODB_URI" --drop "$TEMP_DIR/mongodb_backup_${TIMESTAMP}"

    # Cleanup
    rm -rf "$TEMP_DIR"

    log "MongoDB restore completed"
}

# Restore Redis
restore_redis() {
    log "Restoring Redis..."
    REDIS_BACKUP="${BACKUP_DIR}/redis/redis_backup_${TIMESTAMP}.rdb"

    if [ ! -f "$REDIS_BACKUP" ]; then
        log "ERROR: Redis backup not found: $REDIS_BACKUP"
        return 1
    fi

    # Stop Redis
    systemctl stop redis-server

    # Restore dump
    cp "$REDIS_BACKUP" /var/lib/redis/dump.rdb
    chown redis:redis /var/lib/redis/dump.rdb

    # Start Redis
    systemctl start redis-server

    log "Redis restore completed"
}

# Restore Application
restore_application() {
    log "Restoring application files..."
    APP_BACKUP="${BACKUP_DIR}/application/app_backup_${TIMESTAMP}.tar.gz"

    if [ ! -f "$APP_BACKUP" ]; then
        log "ERROR: Application backup not found: $APP_BACKUP"
        return 1
    fi

    # Stop services
    systemctl stop newsagent

    # Restore files
    tar -xzf "$APP_BACKUP" -C /var/www/newsagent

    # Start services
    systemctl start newsagent

    log "Application restore completed"
}

# Execute restore based on type
case "$RESTORE_TYPE" in
    mongodb)
        restore_mongodb
        ;;
    redis)
        restore_redis
        ;;
    application)
        restore_application
        ;;
    all)
        restore_mongodb
        restore_redis
        restore_application
        ;;
    *)
        echo "Invalid restore type: $RESTORE_TYPE"
        echo "Valid types: mongodb, redis, application, all"
        exit 1
        ;;
esac

log "Restore process completed"

exit 0
