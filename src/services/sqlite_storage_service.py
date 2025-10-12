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

    def __init__(self, db_path: str = "data/news_articles.db"):
        """Initialize SQLite storage service."""
        self.db_path = db_path
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
                source_type TEXT,
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
            metadata_json = json.dumps(article.metadata) if hasattr(article, 'metadata') and article.metadata else None

            # Insert or replace article
            cursor.execute('''
                INSERT OR REPLACE INTO articles (
                    id, title, content, summary, url, source_name, source_type,
                    published_at, collected_at, author, category, tags,
                    sentiment, bias_score, word_count, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.id,
                article.title,
                article.content,
                article.summary or '',
                article.url,
                article.source_name,
                article.source_type.value if hasattr(article, 'source_type') and article.source_type else '',
                article.published_at.isoformat() if article.published_at else None,
                article.collected_at.isoformat() if hasattr(article, 'collected_at') and article.collected_at else datetime.now().isoformat(),
                article.author if hasattr(article, 'author') else '',
                article.category,
                tags_json,
                article.sentiment.value if hasattr(article, 'sentiment') and article.sentiment else None,
                article.bias_score if hasattr(article, 'bias_score') else None,
                article.word_count if hasattr(article, 'word_count') else len(article.content.split()),
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
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Error getting article {article_id}: {str(e)}")
            return None

    async def get_articles(
        self,
        limit: int = 50,
        offset: int = 0,
        source_name: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get articles with optional filtering."""
        if not self.is_connected():
            return []

        try:
            cursor = self.conn.cursor()

            # Build query
            query = 'SELECT * FROM articles WHERE 1=1'
            params = []

            if source_name:
                query += ' AND source_name = ?'
                params.append(source_name)

            if category:
                query += ' AND category = ?'
                params.append(category)

            if sentiment:
                query += ' AND sentiment = ?'
                params.append(sentiment)

            query += ' ORDER BY published_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            articles = [dict(row) for row in rows]
            return articles

        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return []

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
                ORDER BY a.published_at DESC
                LIMIT ?
            ''', (query, limit))

            rows = cursor.fetchall()
            articles = [dict(row) for row in rows]

            return articles

        except Exception as e:
            logger.error(f"Error searching articles: {str(e)}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self.is_connected():
            return {}

        try:
            cursor = self.conn.cursor()

            # Total articles
            cursor.execute('SELECT COUNT(*) as count FROM articles')
            total_articles = cursor.fetchone()['count']

            # Articles by source
            cursor.execute('''
                SELECT source_name, COUNT(*) as count
                FROM articles
                GROUP BY source_name
                ORDER BY count DESC
            ''')
            articles_by_source = {row['source_name']: row['count'] for row in cursor.fetchall()}

            # Articles by sentiment
            cursor.execute('''
                SELECT sentiment, COUNT(*) as count
                FROM articles
                WHERE sentiment IS NOT NULL
                GROUP BY sentiment
            ''')
            articles_by_sentiment = {row['sentiment']: row['count'] for row in cursor.fetchall()}

            # Articles by category
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM articles
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            ''')
            articles_by_category = {row['category']: row['count'] for row in cursor.fetchall()}

            return {
                'total_articles': total_articles,
                'articles_by_source': articles_by_source,
                'articles_by_sentiment': articles_by_sentiment,
                'articles_by_category': articles_by_category,
                'database_size': Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}


# Global instance
sqlite_storage = SQLiteStorageService()
