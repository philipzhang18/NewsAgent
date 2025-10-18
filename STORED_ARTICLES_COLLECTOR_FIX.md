# Stored Articles Collector Field Fix

## Issue Summary

### Problem 1: Missing Columns in Stored Articles Table
**Description**: The Stored Articles data table was missing `source_name` and `collector` columns, making it difficult to identify where articles came from and how they were collected.

**Impact**: Users could not see the source or collection method for stored articles.

### Problem 2: Collector Field Showing "N/A"
**Description**: After adding the collector column, all articles were showing "N/A" instead of actual collector values (NewsAPI, RSS, Reddit, Exa AI, Twitter).

**Root Cause**:
1. The API endpoint `/api/news/articles` was not including the `collector` field when mapping database articles to JSON responses
2. Existing articles in the database had NULL or empty collector values

## Solutions Implemented

### 1. Frontend Update (dashboard.html)
**File**: `src/templates/dashboard.html`

**Changes**:
- Added "Source Name" column header (line 868)
- Added "Collector" column header (line 869)
- Added source_name badge display (lines 896-898)
- Added collector badge display (lines 899-901)
- Adjusted column widths to accommodate new fields

**Result**: Table now displays both source_name and collector with color-coded badges.

### 2. API Mapping Fix (news_api.py)
**File**: `src/api/news_api.py`

**Changes**:
- Line 288: Added `"collector": article.get('collector') or ''` to database article mapping
- Line 329: Added `"collector": article.collector if hasattr(article, 'collector') else ''` to collected article mapping

**Result**: API now properly exposes the collector field in all responses.

### 3. Database Migration (update_collector_field.py)
**File**: `update_collector_field.py` (new file)

**Purpose**: Backfill collector values for existing articles in the database by inferring collector type from source_name patterns.

**Pattern Matching Logic**:
```python
- Reddit/r/* → "Reddit"
- Twitter/@* → "Twitter"
- Exa AI Search → "Exa AI"
- Guardian, BBC, Reuters, Al Jazeera, TechCrunch → "RSS"
- CNN, Bloomberg, Forbes, etc. → "NewsAPI"
- Other sources → "NewsAPI" (default)
```

**Execution Results**:
```
Total articles updated: 1109
- NewsAPI: 920 articles (83%)
- RSS: 93 articles (8%)
- Reddit: 48 articles (4%)
- Exa AI: 48 articles (4%)
```

## Files Modified

1. `src/templates/dashboard.html` - Added source_name and collector columns to Stored Articles table
2. `src/api/news_api.py` - Fixed API mapping to include collector field
3. `update_collector_field.py` - Created database migration script (NEW FILE)

## Testing Performed

### 1. API Verification
```bash
curl -s "http://localhost:5000/api/news/articles?limit=5"
```
**Result**: Confirmed collector field is now present in API responses with correct values.

### 2. Database Verification
```sql
SELECT collector, COUNT(*) FROM articles GROUP BY collector;
```
**Result**: All 1109 articles now have proper collector values, no NULL or "N/A" values.

### 3. Frontend Verification
**Action**: Viewed "Stored Articles" modal on Dashboard
**Result**: Both source_name and collector columns display correctly with color-coded badges.

## Migration Instructions

If you need to run the migration script on a new database:

```bash
cd D:\AI\cursor\starone
python update_collector_field.py
```

**Note**: The script is idempotent - it only updates articles with NULL, empty, or "Unknown" collector values.

## Future Improvements

1. **Automated Collector Assignment**: All new collectors (RSS, Reddit, Twitter, Exa AI, NewsAPI) now automatically set the `collector` field when creating articles, so this migration should only be needed once for existing data.

2. **Source Display Enhancement**: The `source_display` field already provides a formatted version like "CNN-API News", "Reddit-Social News", etc.

3. **Collector Filtering**: Consider adding a filter dropdown to allow users to filter articles by collector type.

## Commit Message

```
fix: Add source_name and collector columns to Stored Articles table

- Add source_name and collector columns to Stored Articles table UI
- Fix API mapping to include collector field in responses
- Create database migration script to backfill collector values
- Update 1109 existing articles with proper collector values

Closes #issue_number
```

## Related Files

- Database schema: `src/services/sqlite_storage_service.py` (lines 48-110)
- RSS collector: `src/collectors/rss_collector.py` (line 101)
- Exa collector: `src/collectors/exa_collector.py` (line 227)
- Reddit collector: `src/collectors/reddit_collector.py`
- Twitter collector: `src/collectors/twitter_collector.py`

## Verification Commands

```bash
# Check database collector distribution
python -c "import sqlite3; conn = sqlite3.connect('data/news_articles.db'); cursor = conn.cursor(); cursor.execute('SELECT collector, COUNT(*) as count FROM articles GROUP BY collector ORDER BY count DESC'); [print(f'{row[0]:20} {row[1]:5} articles') for row in cursor.fetchall()]; conn.close()"

# Test API endpoint
curl -s "http://localhost:5000/api/news/articles?limit=3" | python -m json.tool

# View specific article fields
curl -s "http://localhost:5000/api/news/articles?limit=1" | python -c "import sys, json; article = json.load(sys.stdin)['data']['articles'][0]; print(f\"Source: {article.get('source_name')}\"); print(f\"Collector: {article.get('collector')}\")"
```

---

**Date**: 2025-01-19
**Author**: Claude Code
**Status**: ✅ Completed and Verified
