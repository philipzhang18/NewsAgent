"""
SQLite-based local storage service for news articles.
Provides offline storage and retrieval functionality.
"""

import sqlite3
import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio

from ..models.news_models import NewsArticle

logger = logging.getLogger(__name__)


class SQLiteStorageService:
    """Local SQLite storage for news articles - works completely offline."""

    # Maximum number of articles to store
    MAX_ARTICLES = 10000

    def __init__(self, db_path: str = None):
        """Initialize SQLite storage service."""
        from ..config.settings import settings
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_db_directory()

    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> bool:
        """Connect to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA cache_size=-64000")
            self._create_tables()
            logger.info(f"Successfully connected to SQLite database at {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {str(e)}")
            return False

    def _create_tables(self):
        """Create necessary database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Articles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                url TEXT,
                source_name TEXT,
                collector TEXT,
                source_type TEXT,
                source_display TEXT,
                published_at TEXT,
                collected_at TEXT,
                author TEXT,
                category TEXT,
                tags TEXT,
                sentiment TEXT,
                bias_score REAL,
                word_count INTEGER,
                metadata TEXT
            )
        ''')

        # Add source_display column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN source_display TEXT")
            logger.info("Added source_display column to articles table")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add collector column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN collector TEXT")
            logger.info("Added collector column to articles table")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Create indexes for better search performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_name ON articles(source_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_published_at ON articles(published_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON articles(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment ON articles(sentiment)')

        # Full-text search table
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                id UNINDEXED,
                title,
                content,
                summary,
                tags
            )
        ''')

        self.conn.commit()
        logger.info("Database tables created successfully")

    def disconnect(self):
        """Disconnect from SQLite database."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from SQLite database")

    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self.conn is not None

    async def _cleanup_old_articles(self):
        """Remove oldest articles when exceeding MAX_ARTICLES limit."""
        if not self.is_connected():
            return

        try:
            cursor = self.conn.cursor()

            # Count total articles
            cursor.execute('SELECT COUNT(*) as count FROM articles')
            total_count = cursor.fetchone()['count']

            if total_count > self.MAX_ARTICLES:
                # Calculate how many to delete
                to_delete = total_count - self.MAX_ARTICLES

                # Delete oldest articles (prioritize those without published_at, then oldest by date)
                cursor.execute('''
                    DELETE FROM articles
                    WHERE id IN (
                        SELECT id FROM articles
                        ORDER BY
                            CASE WHEN published_at IS NULL THEN 0 ELSE 1 END,
                            published_at ASC
                        LIMIT ?
                    )
                ''', (to_delete,))

                # Also clean up FTS table
                cursor.execute('''
                    DELETE FROM articles_fts
                    WHERE id NOT IN (SELECT id FROM articles)
                ''')

                self.conn.commit()
                logger.info(f"Cleaned up {to_delete} old articles (total was {total_count}, now {self.MAX_ARTICLES})")

        except Exception as e:
            logger.error(f"Error cleaning up old articles: {str(e)}")

    async def save_article(self, article: NewsArticle) -> bool:
        """Save a single article to database."""
        if not self.is_connected():
            logger.warning("Not connected to database")
            return False

        try:
            cursor = self.conn.cursor()

            # Convert tags list to JSON string
            tags_json = json.dumps(article.tags) if article.tags else None

            # Convert metadata to JSON string
            metadata_json = json.dumps(article.metadata) if article.metadata else None

            # Use source_display from article or generate it
            if article.source_display:
                source_display = article.source_display
            else:
                # Generate source_display field (e.g., "CNN-RSS News", "NewsAPI-API News")
                source_type_str = article.source_type.value if article.source_type else 'unknown'
                source_type_map = {
                    'rss': 'RSS',
                    'api': 'API',
                    'social_media': 'Social',
                    'web': 'Web',
                    'unknown': 'Unknown'
                }
                source_type_label = source_type_map.get(source_type_str, source_type_str.upper())
                source_display = f"{article.source_name}-{source_type_label} News" if article.source_name else f"{source_type_label} News"

            # Insert or replace article
            cursor.execute('''
                INSERT OR REPLACE INTO articles (
                    id, title, content, summary, url, source_name, collector, source_type, source_display,
                    published_at, collected_at, author, category, tags,
                    sentiment, bias_score, word_count, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.id,
                article.title,
                article.content,
                article.summary or '',
                article.url,
                article.source_name,
                article.collector or '',
                article.source_type.value if article.source_type else 'unknown',
                source_display,
                article.published_at.isoformat() if article.published_at else None,
                article.collected_at.isoformat() if article.collected_at else datetime.now().isoformat(),
                article.author or '',
                article.category,
                tags_json,
                article.sentiment.value if article.sentiment else None,
                article.bias_score,
                article.word_count if article.word_count else len(article.content.split()),
                metadata_json
            ))

            # Update FTS table
            cursor.execute('''
                INSERT OR REPLACE INTO articles_fts (id, title, content, summary, tags)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                article.id,
                article.title,
                article.content,
                article.summary or '',
                ' '.join(article.tags) if article.tags else ''
            ))

            self.conn.commit()
            logger.debug(f"Saved article: {article.id}")
            return True

        except Exception as e:
            logger.error(f"Error saving article {article.id}: {str(e)}")
            return False

    async def save_articles(self, articles: List[NewsArticle]) -> int:
        """Save multiple articles to database."""
        if not self.is_connected():
            logger.warning("Not connected to database")
            return 0

        saved_count = 0
        for article in articles:
            if await self.save_article(article):
                saved_count += 1

        # Clean up old articles if limit exceeded
        await self._cleanup_old_articles()

        logger.info(f"Saved {saved_count}/{len(articles)} articles to database")
        return saved_count

    async def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get a single article by ID."""
        if not self.is_connected():
            return None

        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
            row = cursor.fetchone()

            if row:
                return self._normalize_row(row)
            return None

        except Exception as e:
            logger.error(f"Error getting article {article_id}: {str(e)}")
            return None

    def _normalize_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a normalized article dict."""
        data = dict(row)
        if data.get("tags") and isinstance(data["tags"], str):
            try:
                data["tags"] = json.loads(data["tags"])
            except json.JSONDecodeError:
                data["tags"] = []
        if data.get("metadata") and isinstance(data["metadata"], str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}
        return data

    async def get_articles(
        self,
        limit: int = 50,
        offset: int = 0,
        skip: Optional[int] = None,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get articles with optional filtering."""
        if not self.is_connected():
            return []

        if skip is not None:
            offset = skip

        try:
            cursor = self.conn.cursor()

            query = 'SELECT * FROM articles WHERE 1=1'
            params: List[Any] = []

            if source_name:
                query += ' AND source_name = ?'
                params.append(source_name)

            if category:
                query += ' AND category = ?'
                params.append(category)

            if sentiment:
                query += ' AND sentiment = ?'
                params.append(sentiment)

            if start_date:
                query += ' AND COALESCE(published_at, collected_at) >= ?'
                params.append(start_date.isoformat())

            if end_date:
                query += ' AND COALESCE(published_at, collected_at) <= ?'
                params.append(end_date.isoformat())

            query += ' ORDER BY COALESCE(published_at, collected_at) DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._normalize_row(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return []

    async def delete_article(self, article_id: str) -> bool:
        """Delete a single article by ID."""
        if not self.is_connected():
            return False

        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
            cursor.execute('DELETE FROM articles_fts WHERE id = ?', (article_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting article {article_id}: {str(e)}")
            return False

    async def delete_articles_before(self, cutoff_date: datetime) -> int:
        """Delete articles collected or published before cutoff_date."""
        if not self.is_connected():
            return 0

        try:
            cursor = self.conn.cursor()
            cutoff = cutoff_date.isoformat()
            cursor.execute(
                '''
                DELETE FROM articles
                WHERE COALESCE(published_at, collected_at) < ?
                ''',
                (cutoff,),
            )
            deleted = cursor.rowcount
            cursor.execute(
                '''
                DELETE FROM articles_fts
                WHERE id NOT IN (SELECT id FROM articles)
                '''
            )
            self.conn.commit()
            logger.info(f"Deleted {deleted} articles before {cutoff}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting old articles: {str(e)}")
            return 0

    async def query_articles(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Query articles using simple filter dict (source_name, sentiment, category)."""
        return await self.get_articles(
            limit=limit,
            source_name=filters.get("source_name"),
            category=filters.get("category"),
            sentiment=filters.get("sentiment"),
        )

    async def search_articles(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search articles by text query using full-text search."""
        if not self.is_connected():
            return []

        try:
            cursor = self.conn.cursor()

            # Use FTS5 full-text search
            cursor.execute('''
                SELECT a.* FROM articles a
                INNER JOIN articles_fts fts ON a.id = fts.id
                WHERE articles_fts MATCH ?
                ORDER BY COALESCE(a.published_at, a.collected_at) DESC
                LIMIT ?
            ''', (query, limit))

            rows = cursor.fetchall()
            return [self._normalize_row(row) for row in rows]

        except Exception as e:
            logger.error(f"Error searching articles: {str(e)}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics using efficient SQL aggregation."""
        if not self.is_connected():
            return {}

        try:
            cursor = self.conn.cursor()

            # Total articles
            cursor.execute('SELECT COUNT(*) as count FROM articles')
            total_articles = cursor.fetchone()['count']

            # Articles by source (use SQL aggregation)
            cursor.execute('''
                SELECT source_name, COUNT(*) as count
                FROM articles
                WHERE source_name IS NOT NULL
                GROUP BY source_name
                ORDER BY count DESC
            ''')
            articles_by_source = {row['source_name']: row['count'] for row in cursor.fetchall()}

            # Articles by sentiment (use SQL aggregation)
            cursor.execute('''
                SELECT sentiment, COUNT(*) as count
                FROM articles
                WHERE sentiment IS NOT NULL
                GROUP BY sentiment
            ''')
            articles_by_sentiment = {row['sentiment']: row['count'] for row in cursor.fetchall()}

            # Articles by category (use SQL aggregation)
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM articles
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            ''')
            articles_by_category = {row['category']: row['count'] for row in cursor.fetchall()}

            # Get most recent published_at for last_collection
            cursor.execute('''
                SELECT MAX(published_at) as last_published
                FROM articles
                WHERE published_at IS NOT NULL
            ''')
            last_published_row = cursor.fetchone()
            last_published = last_published_row['last_published'] if last_published_row else None

            return {
                'total_articles': total_articles,
                'articles_by_source': articles_by_source,
                'articles_by_sentiment': articles_by_sentiment,
                'articles_by_category': articles_by_category,
                'last_published': last_published,
                'database_size': Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}

    async def count_articles_today(self) -> int:
        """Count articles published or collected today (local date)."""
        if not self.is_connected():
            return 0
        try:
            today = datetime.now().date().isoformat()
            cursor = self.conn.cursor()
            cursor.execute(
                '''
                SELECT COUNT(*) as count FROM articles
                WHERE COALESCE(published_at, collected_at) >= ?
                ''',
                (today,),
            )
            return cursor.fetchone()['count']
        except Exception as e:
            logger.error(f"Error counting today's articles: {e}")
            return 0


# Global instance
sqlite_storage = SQLiteStorageService()
