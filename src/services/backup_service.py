"""
Backup and recovery service for data persistence.
"""

import logging
import os
import shutil
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict
import subprocess
import json

logger = logging.getLogger(__name__)


class BackupService:
    """Service for backing up and restoring application data."""

    def __init__(
        self,
        backup_dir: str = '/backup',
        retention_days: int = 30,
        mongodb_uri: Optional[str] = None,
        redis_host: str = 'localhost',
        redis_port: int = 6379
    ):
        """
        Initialize backup service.

        Args:
            backup_dir: Base directory for backups
            retention_days: Number of days to retain backups
            mongodb_uri: MongoDB connection URI
            redis_host: Redis host
            redis_port: Redis port
        """
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/news_agent')
        self.redis_host = redis_host
        self.redis_port = redis_port

        # Create backup directories
        self.mongodb_backup_dir = self.backup_dir / 'mongodb'
        self.redis_backup_dir = self.backup_dir / 'redis'
        self.app_backup_dir = self.backup_dir / 'application'

        for dir_path in [self.mongodb_backup_dir, self.redis_backup_dir, self.app_backup_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Backup service initialized: {self.backup_dir}")

    def backup_mongodb(self, compress: bool = True) -> Dict:
        """
        Backup MongoDB database.

        Args:
            compress: Whether to compress backup

        Returns:
            Backup information dictionary
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_name = f"mongodb_backup_{timestamp}"
        backup_path = self.mongodb_backup_dir / backup_name

        try:
            logger.info(f"Starting MongoDB backup: {backup_name}")

            # Run mongodump
            cmd = [
                'mongodump',
                '--uri', self.mongodb_uri,
                '--out', str(backup_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Compress if requested
            if compress:
                archive_path = f"{backup_path}.tar.gz"
                with tarfile.open(archive_path, 'w:gz') as tar:
                    tar.add(backup_path, arcname=backup_name)

                # Remove uncompressed backup
                shutil.rmtree(backup_path)

                backup_file = archive_path
                logger.info(f"MongoDB backup compressed: {archive_path}")
            else:
                backup_file = str(backup_path)

            # Get file size
            if compress:
                size_bytes = os.path.getsize(backup_file)
            else:
                size_bytes = sum(f.stat().st_size for f in Path(backup_file).rglob('*') if f.is_file())

            info = {
                'type': 'mongodb',
                'timestamp': timestamp,
                'path': backup_file,
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / (1024 * 1024), 2),
                'compressed': compress,
                'success': True
            }

            logger.info(f"MongoDB backup completed: {size_bytes} bytes")
            return info

        except subprocess.CalledProcessError as e:
            logger.error(f"MongoDB backup failed: {e.stderr}")
            return {
                'type': 'mongodb',
                'timestamp': timestamp,
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"MongoDB backup error: {str(e)}")
            return {
                'type': 'mongodb',
                'timestamp': timestamp,
                'success': False,
                'error': str(e)
            }

    def backup_redis(self) -> Dict:
        """
        Backup Redis data.

        Returns:
            Backup information dictionary
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_name = f"redis_backup_{timestamp}.rdb"
        backup_path = self.redis_backup_dir / backup_name

        try:
            logger.info(f"Starting Redis backup: {backup_name}")

            # Trigger Redis BGSAVE
            cmd = ['redis-cli', '-h', self.redis_host, '-p', str(self.redis_port), 'BGSAVE']
            subprocess.run(cmd, check=True, capture_output=True)

            # Wait for save to complete
            import time
            max_wait = 60  # seconds
            waited = 0

            while waited < max_wait:
                cmd = ['redis-cli', '-h', self.redis_host, '-p', str(self.redis_port), 'LASTSAVE']
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                # Wait a bit and check again
                time.sleep(1)
                waited += 1

            # Copy Redis dump file
            redis_dump = '/var/lib/redis/dump.rdb'  # Default Redis dump location
            if os.path.exists(redis_dump):
                shutil.copy2(redis_dump, backup_path)
                size_bytes = os.path.getsize(backup_path)

                info = {
                    'type': 'redis',
                    'timestamp': timestamp,
                    'path': str(backup_path),
                    'size_bytes': size_bytes,
                    'size_mb': round(size_bytes / (1024 * 1024), 2),
                    'success': True
                }

                logger.info(f"Redis backup completed: {size_bytes} bytes")
                return info
            else:
                raise FileNotFoundError(f"Redis dump file not found: {redis_dump}")

        except Exception as e:
            logger.error(f"Redis backup error: {str(e)}")
            return {
                'type': 'redis',
                'timestamp': timestamp,
                'success': False,
                'error': str(e)
            }

    def backup_application_files(self, include_logs: bool = False) -> Dict:
        """
        Backup application files.

        Args:
            include_logs: Whether to include log files

        Returns:
            Backup information dictionary
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_name = f"app_backup_{timestamp}.tar.gz"
        backup_path = self.app_backup_dir / backup_name

        try:
            logger.info(f"Starting application backup: {backup_name}")

            # Files/directories to backup
            app_root = Path('/var/www/newsagent')  # Adjust as needed
            items_to_backup = [
                '.env',
                'src/',
                'config/',
                'scripts/',
                'requirements.txt'
            ]

            if include_logs:
                items_to_backup.append('logs/')

            # Create tar archive
            with tarfile.open(backup_path, 'w:gz') as tar:
                for item in items_to_backup:
                    item_path = app_root / item
                    if item_path.exists():
                        tar.add(item_path, arcname=item)

            size_bytes = os.path.getsize(backup_path)

            info = {
                'type': 'application',
                'timestamp': timestamp,
                'path': str(backup_path),
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / (1024 * 1024), 2),
                'success': True,
                'includes_logs': include_logs
            }

            logger.info(f"Application backup completed: {size_bytes} bytes")
            return info

        except Exception as e:
            logger.error(f"Application backup error: {str(e)}")
            return {
                'type': 'application',
                'timestamp': timestamp,
                'success': False,
                'error': str(e)
            }

    def backup_all(self) -> Dict:
        """
        Backup all data (MongoDB, Redis, application files).

        Returns:
            Combined backup information
        """
        logger.info("Starting full backup")

        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'backups': []
        }

        # MongoDB backup
        mongodb_result = self.backup_mongodb(compress=True)
        results['backups'].append(mongodb_result)

        # Redis backup
        redis_result = self.backup_redis()
        results['backups'].append(redis_result)

        # Application backup
        app_result = self.backup_application_files(include_logs=False)
        results['backups'].append(app_result)

        # Calculate totals
        results['total_size_mb'] = sum(
            b.get('size_mb', 0) for b in results['backups'] if b.get('success')
        )
        results['success_count'] = sum(1 for b in results['backups'] if b.get('success'))
        results['failed_count'] = sum(1 for b in results['backups'] if not b.get('success'))

        logger.info(f"Full backup completed: {results['success_count']}/{len(results['backups'])} successful")

        return results

    def restore_mongodb(self, backup_path: str) -> bool:
        """
        Restore MongoDB from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Restoring MongoDB from: {backup_path}")

            # Extract if compressed
            if backup_path.endswith('.tar.gz'):
                extract_dir = Path(backup_path).parent / 'temp_extract'
                extract_dir.mkdir(exist_ok=True)

                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(extract_dir)

                # Find the backup directory
                backup_dirs = list(extract_dir.glob('mongodb_backup_*'))
                if not backup_dirs:
                    raise ValueError("No backup directory found in archive")

                restore_path = backup_dirs[0]
            else:
                restore_path = backup_path

            # Run mongorestore
            cmd = [
                'mongorestore',
                '--uri', self.mongodb_uri,
                '--drop',  # Drop existing collections
                str(restore_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Cleanup
            if backup_path.endswith('.tar.gz'):
                shutil.rmtree(extract_dir)

            logger.info("MongoDB restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"MongoDB restore failed: {str(e)}")
            return False

    def restore_redis(self, backup_path: str) -> bool:
        """
        Restore Redis from backup.

        Args:
            backup_path: Path to backup .rdb file

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Restoring Redis from: {backup_path}")

            # Stop Redis (requires sudo/proper permissions)
            subprocess.run(['systemctl', 'stop', 'redis-server'], check=True)

            # Copy backup to Redis data directory
            redis_dump = '/var/lib/redis/dump.rdb'
            shutil.copy2(backup_path, redis_dump)
            os.chown(redis_dump, -1, -1)  # Set proper ownership

            # Start Redis
            subprocess.run(['systemctl', 'start', 'redis-server'], check=True)

            logger.info("Redis restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Redis restore failed: {str(e)}")
            # Attempt to start Redis even if restore failed
            try:
                subprocess.run(['systemctl', 'start', 'redis-server'])
            except:
                pass
            return False

    def cleanup_old_backups(self) -> Dict:
        """
        Remove backups older than retention period.

        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        removed_count = 0
        removed_size = 0

        logger.info(f"Cleaning up backups older than {self.retention_days} days")

        for backup_subdir in [self.mongodb_backup_dir, self.redis_backup_dir, self.app_backup_dir]:
            for backup_file in backup_subdir.iterdir():
                if backup_file.is_file():
                    # Check file age
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)

                    if file_time < cutoff_date:
                        size = backup_file.stat().st_size
                        backup_file.unlink()
                        removed_count += 1
                        removed_size += size
                        logger.info(f"Removed old backup: {backup_file.name}")

        return {
            'removed_count': removed_count,
            'removed_size_mb': round(removed_size / (1024 * 1024), 2),
            'retention_days': self.retention_days
        }

    def list_backups(self) -> Dict:
        """
        List all available backups.

        Returns:
            Dictionary of backups by type
        """
        backups = {
            'mongodb': [],
            'redis': [],
            'application': []
        }

        # MongoDB backups
        for backup_file in self.mongodb_backup_dir.iterdir():
            if backup_file.is_file() or backup_file.is_dir():
                backups['mongodb'].append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size_mb': round(self._get_size(backup_file) / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                })

        # Redis backups
        for backup_file in self.redis_backup_dir.iterdir():
            if backup_file.is_file():
                backups['redis'].append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                })

        # Application backups
        for backup_file in self.app_backup_dir.iterdir():
            if backup_file.is_file():
                backups['application'].append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                })

        return backups

    def _get_size(self, path: Path) -> int:
        """Get total size of file or directory."""
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())


# Global instance
backup_service = BackupService()
