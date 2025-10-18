"""
Update collector field for existing articles in the database.

This script infers the collector type based on source_name patterns:
- Reddit/r/* → Reddit
- Twitter/@* → Twitter
- Exa AI Search → Exa AI
- RSS feeds → RSS
- Others → Unknown
"""

import asyncio
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).parent / "data" / "news_articles.db"


def infer_collector(source_name: str) -> str:
    """Infer collector type from source_name."""
    if not source_name:
        return "Unknown"

    source_lower = source_name.lower()

    # Pattern matching
    if "reddit" in source_lower or source_name.startswith("Reddit/r/"):
        return "Reddit"
    elif "twitter" in source_lower or source_name.startswith("Twitter/@"):
        return "Twitter"
    elif "exa" in source_lower:
        return "Exa AI"
    elif any(rss_indicator in source_lower for rss_indicator in ["guardian", "bbc", "reuters", "al jazeera", "techcrunch"]):
        return "RSS"
    elif any(newsapi_indicator in source_name for newsapi_indicator in [
        "CNN", "ABC News", "Associated Press", "Bloomberg", "CNBC", "Forbes", "NBC News",
        "CBS News", "Fox News", "USA Today", "Washington Post", "New York Times",
        "Wall Street Journal", "TIME", "Newsweek", "Wired", "TechCrunch", "The Verge",
        "Ars Technica", "Engadget", "Mashable", "Polygon", "IGN", "Google News"
    ]):
        return "NewsAPI"
    else:
        # Default to NewsAPI for unknown sources (likely from NewsAPI)
        return "NewsAPI"


async def update_collectors():
    """Update collector field for all articles."""
    try:
        # Connect to database
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all articles without collector value or with 'Unknown' collector
        cursor.execute("""
            SELECT id, source_name, collector
            FROM articles
            WHERE collector IS NULL OR collector = '' OR collector = 'Unknown'
        """)

        articles = cursor.fetchall()
        logger.info(f"Found {len(articles)} articles without collector value")

        if len(articles) == 0:
            logger.info("No articles need updating")
            return

        # Update each article
        updated_count = 0
        collector_stats = {}

        for article in articles:
            article_id = article['id']
            source_name = article['source_name']

            # Infer collector
            collector = infer_collector(source_name)

            # Update database
            cursor.execute("""
                UPDATE articles
                SET collector = ?
                WHERE id = ?
            """, (collector, article_id))

            updated_count += 1
            collector_stats[collector] = collector_stats.get(collector, 0) + 1

        # Commit changes
        conn.commit()

        logger.info(f"Successfully updated {updated_count} articles")
        logger.info("Collector distribution:")
        for collector, count in sorted(collector_stats.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {collector}: {count} articles")

        conn.close()

    except Exception as e:
        logger.error(f"Error updating collectors: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(update_collectors())
    logger.info("Update complete!")
