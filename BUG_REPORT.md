# Bug Report - News Agent Application
**Generated:** 2025-10-16
**Analysis Method:** Manual code review + Static analysis
**Playwright MCP Status:** Installed in virtual environment (Chromium browser ready)

---

## Executive Summary

After comprehensive code analysis of the News Agent application, **15 critical and high-priority bugs** were identified across multiple components. These issues range from runtime errors, async/event loop problems, to security vulnerabilities and configuration issues.

### Severity Breakdown
- **Critical**: 5 bugs (application crashes, data loss risks)
- **High**: 6 bugs (functionality failures, performance issues)
- **Medium**: 4 bugs (minor errors, edge cases)

---

## Critical Bugs (Priority 1)

### 🔴 BUG #1: Event Loop Reuse Error in Flask Routes
**Location:** `src/app.py:23-30`
**Severity:** CRITICAL
**Impact:** Application crashes when handling multiple concurrent requests

**Description:**
```python
def run_async(coro):
    """Helper to run async functions in sync Flask context."""
    try:
        loop = asyncio.get_event_loop()  # ❌ WRONG: Reuses same loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
```

**Problem:**
- `asyncio.get_event_loop()` returns the existing event loop which may already be running
- Calling `run_until_complete()` on a running loop causes `RuntimeError`
- In multi-threaded Flask applications, this leads to event loop conflicts

**Fix:**
```python
def run_async(coro):
    """Helper to run async functions in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Test Case:**
```python
# Send multiple concurrent requests to /api/monitoring/health
# Without fix: RuntimeError: This event loop is already running
# With fix: All requests complete successfully
```

---

### 🔴 BUG #2: AsyncIO Task Creation Without Event Loop
**Location:** `src/app.py:160`
**Severity:** CRITICAL
**Impact:** Background tasks fail to start, collection never runs

**Description:**
```python
@app.route('/api/start', methods=['POST'])
def start_service():
    async def _start():
        if not collector_service.is_running:
            await collector_service.initialize_collectors()
            asyncio.create_task(collector_service.start_collection_cycle())  # ❌ NO LOOP!
```

**Problem:**
- `asyncio.create_task()` is called inside `run_async()` which closes the loop immediately
- The task is created but never scheduled for execution
- Collection service appears to start but never actually collects news

**Fix:**
```python
@app.route('/api/start', methods=['POST'])
def start_service():
    try:
        import threading

        def run_collection_in_thread():
            async def _start():
                await collector_service.initialize_collectors()
                await collector_service.start_collection_cycle()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start())

        # Start collection in background thread
        collector_thread = threading.Thread(target=run_collection_in_thread, daemon=True)
        collector_thread.start()

        return jsonify({
            "success": True,
            "message": "Service started successfully"
        })
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
```

---

### 🔴 BUG #3: Schedule Library Not Async-Compatible
**Location:** `src/services/news_collector_service.py:66-78`
**Severity:** CRITICAL
**Impact:** Scheduled collections never execute correctly

**Description:**
```python
async def start_collection_cycle(self):
    # Schedule collection tasks
    for collector in self.collectors.values():
        schedule.every(collector.source.collection_interval).seconds.do(
            self._run_collector, collector  # ❌ schedule.do() doesn't support async
        )

    while self.is_running:
        schedule.run_pending()  # ❌ This blocks the event loop
        await asyncio.sleep(1)
```

**Problem:**
- `schedule` library is synchronous and blocks the async event loop
- `schedule.do()` cannot call async functions properly
- `schedule.run_pending()` blocks, preventing other async tasks from running

**Fix:**
```python
async def start_collection_cycle(self):
    """Start the news collection cycle using async scheduling."""
    if self.is_running:
        logger.warning("News collection service is already running")
        return

    self.is_running = True
    logger.info("Starting news collection service...")

    try:
        # Run initial collection
        await self._run_all_collectors()

        # Create periodic tasks for each collector
        tasks = []
        for collector in self.collectors.values():
            interval = collector.source.collection_interval
            task = asyncio.create_task(self._periodic_collection(collector, interval))
            tasks.append(task)

        # Wait for all tasks (they run indefinitely until is_running = False)
        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.error(f"Error in collection cycle: {str(e)}")
    finally:
        self.is_running = False

async def _periodic_collection(self, collector, interval_seconds):
    """Run a collector periodically."""
    while self.is_running:
        try:
            await self._run_collector(collector)
        except Exception as e:
            logger.error(f"Error in periodic collection for {collector.collector_id}: {str(e)}")

        await asyncio.sleep(interval_seconds)
```

---

### 🔴 BUG #4: SQLite Connection Thread Safety Issue
**Location:** `src/services/sqlite_storage_service.py:36`
**Severity:** CRITICAL
**Impact:** Database corruption in multi-threaded Flask app

**Description:**
```python
def connect(self) -> bool:
    try:
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)  # ⚠️ DANGEROUS!
```

**Problem:**
- `check_same_thread=False` disables SQLite's thread safety checks
- SQLite connections are NOT thread-safe by default
- Flask runs multiple threads for handling requests
- Concurrent database writes can corrupt the database

**Fix:**
```python
import threading
from contextlib import contextmanager

class SQLiteStorageService:
    def __init__(self, db_path: str = "data/news_articles.db"):
        self.db_path = db_path
        self._local = threading.local()  # Thread-local storage
        self._ensure_db_directory()

    def _get_connection(self):
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database operations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    async def save_article(self, article: NewsArticle) -> bool:
        """Save a single article to database."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(''' ... ''')
            return True
        except Exception as e:
            logger.error(f"Error saving article {article.id}: {str(e)}")
            return False
```

---

### 🔴 BUG #5: API Key Exposure in .env File
**Location:** `.env file` (line 2, 12-16)
**Severity:** CRITICAL (SECURITY)
**Impact:** API keys exposed in version control

**Description:**
The `.env` file contains real API keys that are checked into git:
```env
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
NEWS_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWITTER_BEARER_TOKEN=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Problem:**
- API keys should NEVER be committed to version control
- These keys are now publicly exposed and should be revoked
- Anyone with access to the repository can use these credentials

**IMMEDIATE ACTIONS REQUIRED:**
1. **Revoke all exposed API keys immediately**
   - OpenAI: https://platform.openai.com/api-keys
   - NewsAPI: https://newsapi.org/account
   - Twitter: https://developer.twitter.com/en/portal/dashboard
   - Reddit: https://www.reddit.com/prefs/apps

2. **Remove .env from git history:**
```bash
# Remove .env from git history (DANGEROUS - backup first!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (coordinate with team first!)
git push origin --force --all
```

3. **Verify .gitignore:**
```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Ensure .env is ignored"
```

4. **Use env.example instead:**
```env
# env.example - Safe to commit
OPENAI_API_KEY=your_openai_key_here
NEWS_API_KEY=your_newsapi_key_here
TWITTER_BEARER_TOKEN=your_twitter_token_here
```

---

## High Priority Bugs (Priority 2)

### 🟠 BUG #6: Missing Error Handling in RSS Feed Parsing
**Location:** `src/collectors/rss_collector.py:38-41`
**Severity:** HIGH
**Impact:** Application crashes on malformed RSS feeds

**Description:**
```python
# Parse RSS feed
feed = self.feed_parser.parse(self.source.url)

if feed.status != 200:  # ❌ feed.status may not exist!
    raise Exception(f"RSS feed returned status {feed.status}")
```

**Problem:**
- Not all RSS feeds have a `status` attribute (e.g., file:// URLs)
- Accessing `feed.status` when it doesn't exist raises `AttributeError`
- Network errors don't set status codes

**Fix:**
```python
async def collect_news(self) -> List[NewsArticle]:
    try:
        logger.info(f"Collecting news from RSS feed: {self.source.url}")

        # Parse RSS feed with timeout
        import urllib.request
        from urllib.error import URLError, HTTPError

        try:
            response = urllib.request.urlopen(self.source.url, timeout=30)
            feed = self.feed_parser.parse(response)
        except (URLError, HTTPError) as e:
            raise Exception(f"Failed to fetch RSS feed: {str(e)}")

        # Check feed validity
        if hasattr(feed, 'status') and feed.status not in [200, 301, 302]:
            raise Exception(f"RSS feed returned status {feed.status}")

        if not feed.entries:
            logger.warning(f"RSS feed {self.source.url} has no entries")
            return []

        # Continue parsing...
```

---

### 🟠 BUG #7: NLTK Data Download Failure Not Handled
**Location:** `src/processors/news_processor.py:34-41`
**Severity:** HIGH
**Impact:** Text processing features silently fail

**Description:**
```python
def _download_nltk_data(self):
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
    except Exception as e:
        logger.warning(f"Could not download NLTK data: {str(e)}")  # ⚠️ Only logs, doesn't prevent usage
```

**Problem:**
- If NLTK data fails to download, subsequent code still tries to use it
- `nltk.corpus.stopwords.words('english')` fails with `LookupError` if data missing
- Application continues but features break silently

**Fix:**
```python
def __init__(self):
    self.openai_client = ...
    self.nltk_available = self._download_nltk_data()
    if not self.nltk_available:
        logger.warning("NLTK features disabled due to missing data")

def _download_nltk_data(self) -> bool:
    """Download required NLTK data and return success status."""
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)

        # Verify data is actually available
        from nltk.corpus import stopwords
        stopwords.words('english')  # Test access
        return True
    except Exception as e:
        logger.error(f"Could not download NLTK data: {str(e)}")
        return False

def _extract_metadata(self, article: NewsArticle) -> NewsArticle:
    try:
        if not article.tags and self.nltk_available:  # ✅ Check availability
            words = article.content.lower().split()
            try:
                from nltk.corpus import stopwords
                stop_words = set(stopwords.words('english'))
            except LookupError:
                logger.warning("NLTK stopwords not available, using basic filtering")
                stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at'}
            # Continue...
```

---

### 🟠 BUG #8: Missing Validation in News API Requests
**Location:** `src/api/news_api.py:368-371`
**Severity:** HIGH
**Impact:** API errors expose error messages, potential DoS

**Description:**
```python
resp = requests.get(endpoint, params=params, timeout=10)
resp.raise_for_status()  # ❌ Can raise exceptions not caught
data = resp.json()       # ❌ No JSON validation
```

**Problem:**
- `raise_for_status()` raises `HTTPError` which may not be caught
- `resp.json()` fails if response isn't valid JSON
- No rate limit handling for NewsAPI (rate limits exist!)
- Timeout of 10s may be too short for slow connections

**Fix:**
```python
import time
from requests.exceptions import RequestException, Timeout, HTTPError

# Add retry logic with exponential backoff
def fetch_with_retry(endpoint, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(endpoint, params=params, timeout=30)

            # Check for rate limiting (429)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                continue

            resp.raise_for_status()

            # Validate JSON response
            try:
                data = resp.json()
            except ValueError as e:
                raise Exception(f"Invalid JSON response: {str(e)}")

            # Validate NewsAPI response structure
            if data.get('status') != 'ok':
                error_msg = data.get('message', 'Unknown error')
                raise Exception(f"NewsAPI error: {error_msg}")

            return data

        except Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff

        except HTTPError as e:
            if e.response.status_code in [500, 502, 503, 504]:
                # Server errors - retry
                logger.warning(f"Server error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            raise

    raise Exception("Max retries exceeded")
```

---

### 🟠 BUG #9: Unclosed Database Connections
**Location:** `src/services/sqlite_storage_service.py:320`
**Severity:** HIGH
**Impact:** Resource leaks, connection pool exhaustion

**Description:**
```python
# Global instance
sqlite_storage = SQLiteStorageService()
```

**Problem:**
- Global SQLite connection is created but never closed
- Connection remains open for entire application lifetime
- In long-running applications, this can cause:
  - File descriptor leaks
  - Lock contention
  - Database corruption if process is killed

**Fix:**
```python
# Add connection pooling and proper cleanup
import atexit

class SQLiteStorageService:
    def __init__(self, db_path: str = "data/news_articles.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_db_directory()

        # Register cleanup on exit
        atexit.register(self.disconnect)

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.disconnect()

    def disconnect(self):
        """Safely disconnect from SQLite database."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Disconnected from SQLite database")
            except Exception as e:
                logger.error(f"Error closing database: {str(e)}")
            finally:
                self.conn = None

# In app.py, add shutdown handler
from flask import Flask

app = Flask(__name__)

@app.teardown_appcontext
def shutdown_db(exception=None):
    """Close database connections when app shuts down."""
    if sqlite_storage.is_connected():
        sqlite_storage.disconnect()
```

---

### 🟠 BUG #10: Race Condition in Article Collection
**Location:** `src/services/news_collector_service.py:96-101`
**Severity:** HIGH
**Impact:** Duplicate articles, data inconsistency

**Description:**
```python
async def _run_collector(self, collector: BaseCollector):
    try:
        if collector.should_collect():
            collection = await collector.start_collection()
            if collection:
                self.collections.append(collection)  # ❌ Not thread-safe!
                self._update_stats(collection)       # ❌ Not atomic!
```

**Problem:**
- Multiple collectors can run concurrently (via `asyncio.gather`)
- `self.collections.append()` is not atomic in async context
- `self._update_stats()` modifies shared state without locking
- Can lead to lost collections or corrupted statistics

**Fix:**
```python
import asyncio

class NewsCollectorService:
    def __init__(self):
        self.collectors: Dict[str, BaseCollector] = {}
        self.collections: List[NewsCollection] = []
        self.is_running = False
        self.collection_stats = {...}
        self._lock = asyncio.Lock()  # Add async lock

    async def _run_collector(self, collector: BaseCollector):
        """Run a single collector with proper synchronization."""
        try:
            if collector.should_collect():
                collection = await collector.start_collection()
                if collection:
                    async with self._lock:  # ✅ Protect shared state
                        self.collections.append(collection)
                        self._update_stats(collection)

                        # Keep only recent collections in memory
                        if len(self.collections) > 100:
                            self.collections = self.collections[-100:]
        except Exception as e:
            logger.error(f"Error running collector {collector.collector_id}: {str(e)}")
```

---

### 🟠 BUG #11: Memory Leak in Article Storage
**Location:** `src/services/news_collector_service.py:99-101`
**Severity:** HIGH
**Impact:** Unbounded memory growth, eventual OOM

**Description:**
```python
if collection:
    self.collections.append(collection)
    self._update_stats(collection)

    # Keep only recent collections in memory
    if len(self.collections) > 100:
        self.collections = self.collections[-100:]  # ⚠️ Only trims here!
```

**Problem:**
- Memory trimming only happens after successful collection
- If collections fail repeatedly, list never gets trimmed
- Each `NewsCollection` can contain up to `MAX_ARTICLES_PER_SOURCE` articles
- With 100 collections × 100 articles = 10,000 articles in memory constantly

**Fix:**
```python
from collections import deque

class NewsCollectorService:
    def __init__(self):
        # Use deque with maxlen for automatic size management
        self.collections = deque(maxlen=100)  # ✅ Auto-trim
        self.collection_stats = {...}

        # Add memory monitoring
        self.max_memory_mb = 500  # 500MB limit

    async def _run_collector(self, collector: BaseCollector):
        try:
            if collector.should_collect():
                collection = await collector.start_collection()
                if collection:
                    async with self._lock:
                        self.collections.append(collection)  # Auto-trims oldest
                        self._update_stats(collection)

                        # Check memory usage periodically
                        if len(self.collections) % 10 == 0:
                            self._check_memory_usage()
        except Exception as e:
            logger.error(f"Error running collector: {str(e)}")

    def _check_memory_usage(self):
        """Monitor and warn about high memory usage."""
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > self.max_memory_mb:
            logger.warning(f"High memory usage: {memory_mb:.1f}MB")
            # Force garbage collection
            import gc
            gc.collect()
```

---

## Medium Priority Bugs (Priority 3)

### 🟡 BUG #12: Hardcoded Date in Mock Data
**Location:** `src/api/news_api.py:403, 759`
**Severity:** MEDIUM
**Impact:** Confusing timestamps in mock responses

**Description:**
```python
"published_at": "2025-10-10T10:00:00Z",  # Hardcoded future date!
"last_updated": "2025-09-23T10:20:00Z"   # Hardcoded past date!
```

**Fix:**
```python
from datetime import datetime, timedelta

# Generate realistic timestamps
now = datetime.utcnow()
mock_articles = [
    {
        "id": "1",
        "title": "OpenAI Releases GPT-5",
        "published_at": (now - timedelta(hours=2)).isoformat() + 'Z',
        # ...
    },
    {
        "id": "2",
        "title": "Google's New AI Model",
        "published_at": (now - timedelta(hours=5)).isoformat() + 'Z',
        # ...
    }
]
```

---

### 🟡 BUG #13: Missing Input Validation on User Inputs
**Location:** `src/api/news_api.py:248-252`
**Severity:** MEDIUM
**Impact:** Potential injection attacks, crashes

**Description:**
```python
@news_api.route('/articles', methods=['GET'])
def get_articles():
    limit = request.args.get('limit', 50, type=int)  # No range check!
    query = request.args.get('q')  # No sanitization!
    country = request.args.get('country', 'us')  # No validation!
```

**Fix:**
```python
from werkzeug.exceptions import BadRequest

@news_api.route('/articles', methods=['GET'])
def get_articles():
    # Validate limit parameter
    try:
        limit = request.args.get('limit', 50, type=int)
        if limit < 1 or limit > 1000:
            raise BadRequest("Limit must be between 1 and 1000")
    except ValueError:
        raise BadRequest("Invalid limit parameter")

    # Sanitize query parameter
    query = request.args.get('q', '').strip()
    if len(query) > 500:
        raise BadRequest("Query too long (max 500 characters)")

    # Validate country code
    country = request.args.get('country', 'us')
    valid_countries = ['us', 'uk', 'ca', 'au', 'in', 'de', 'fr']
    if country not in valid_countries:
        raise BadRequest(f"Invalid country code. Valid: {', '.join(valid_countries)}")

    # Validate category
    category = request.args.get('category')
    if category:
        valid_categories = ['business', 'entertainment', 'general', 'health',
                          'science', 'sports', 'technology']
        if category not in valid_categories:
            raise BadRequest(f"Invalid category. Valid: {', '.join(valid_categories)}")

    # Continue with validated inputs...
```

---

### 🟡 BUG #14: Timezone Handling Issues
**Location:** `src/api/news_api.py:125-138`
**Severity:** MEDIUM
**Impact:** Incorrect timestamp comparisons, sorting errors

**Description:**
```python
def get_timestamp(article):
    dt = article.published_at
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)  # Assumes UTC!
        return dt.timestamp()
    return 0
```

**Problem:**
- Naive datetimes (no timezone) are assumed to be UTC, which may not be true
- Different sources may provide timestamps in different timezones
- Comparing naive and aware datetimes raises TypeError

**Fix:**
```python
from datetime import datetime, timezone
import dateutil.parser

def normalize_datetime(dt):
    """Normalize datetime to UTC timezone-aware."""
    if dt is None:
        return None

    # If string, parse it
    if isinstance(dt, str):
        try:
            dt = dateutil.parser.parse(dt)
        except Exception as e:
            logger.warning(f"Failed to parse datetime: {dt}")
            return None

    # If naive datetime, assume UTC (document this assumption!)
    if dt.tzinfo is None:
        logger.debug(f"Naive datetime encountered, assuming UTC: {dt}")
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt

def get_timestamp(article):
    dt = normalize_datetime(article.published_at)
    return dt.timestamp() if dt else 0
```

---

### 🟡 BUG #15: Inefficient Database Query Pattern
**Location:** `src/services/sqlite_storage_service.py:195-237`
**Severity:** MEDIUM
**Impact:** Slow queries as database grows

**Description:**
```python
async def get_articles(
    self,
    limit: int = 50,
    offset: int = 0,
    source_name: Optional[str] = None,
    category: Optional[str] = None,
    sentiment: Optional[str] = None
) -> List[Dict[str, Any]]:
    # Build query
    query = 'SELECT * FROM articles WHERE 1=1'  # ❌ SELECT *
    params = []

    if source_name:
        query += ' AND source_name = ?'
        params.append(source_name)
    # ...
    query += ' ORDER BY published_at DESC LIMIT ? OFFSET ?'  # ❌ OFFSET is slow for large offsets
```

**Problems:**
1. `SELECT *` retrieves all columns even when not needed
2. `OFFSET` scans all skipped rows, very slow for large offsets
3. No query caching or prepared statements
4. Missing indexes on frequently queried columns

**Fix:**
```python
# Add indexes in _create_tables()
def _create_tables(self):
    cursor = self.conn.cursor()

    # ... existing table creation ...

    # Add composite indexes for common queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_published ON articles(source_name, published_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_category_published ON articles(category, published_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_published ON articles(sentiment, published_at DESC)')

    self.conn.commit()

# Use cursor-based pagination instead of OFFSET
async def get_articles(
    self,
    limit: int = 50,
    last_id: Optional[str] = None,  # Use cursor instead of offset
    source_name: Optional[str] = None,
    category: Optional[str] = None,
    sentiment: Optional[str] = None
) -> Dict[str, Any]:
    """Get articles with cursor-based pagination."""
    if not self.is_connected():
        return {"articles": [], "next_cursor": None}

    try:
        cursor = self.conn.cursor()

        # Select only needed columns
        query = '''
            SELECT id, title, summary, url, source_name, published_at,
                   sentiment, category, bias_score
            FROM articles
            WHERE 1=1
        '''
        params = []

        # Cursor-based pagination
        if last_id:
            query += ' AND id > ?'
            params.append(last_id)

        if source_name:
            query += ' AND source_name = ?'
            params.append(source_name)

        if category:
            query += ' AND category = ?'
            params.append(category)

        if sentiment:
            query += ' AND sentiment = ?'
            params.append(sentiment)

        query += ' ORDER BY id ASC LIMIT ?'
        params.append(limit + 1)  # Fetch one extra to check if more exist

        cursor.execute(query, params)
        rows = cursor.fetchall()

        articles = [dict(row) for row in rows[:limit]]
        next_cursor = articles[-1]['id'] if len(rows) > limit else None

        return {
            "articles": articles,
            "next_cursor": next_cursor,
            "has_more": len(rows) > limit
        }

    except Exception as e:
        logger.error(f"Error getting articles: {str(e)}")
        return {"articles": [], "next_cursor": None}
```

---

## Testing with Playwright

### Setup
Playwright has been successfully installed in your virtual environment. To use it for automated testing:

```bash
# Activate virtual environment
venv\Scripts\activate

# Install Playwright browsers (if not already done)
python -m playwright install chromium

# Run basic test
python -m playwright codegen http://localhost:5000
```

### Recommended Test Cases

Create `tests/test_ui_playwright.py`:

```python
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
    }

def test_homepage_loads(page: Page):
    """Test that homepage loads without errors."""
    page.goto("http://localhost:5000")

    # Check for console errors
    errors = []
    page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)

    # Wait for page to be loaded
    page.wait_for_load_state("networkidle")

    # Verify page title
    expect(page).to_have_title(/News Agent/)

    # Check no JavaScript errors
    assert len(errors) == 0, f"Console errors found: {errors}"

def test_articles_api_endpoint(page: Page):
    """Test articles API endpoint returns valid JSON."""
    response = page.request.get("http://localhost:5000/api/news/articles?limit=10")

    assert response.ok
    data = response.json()
    assert data["success"] == True
    assert "articles" in data["data"]
    assert len(data["data"]["articles"]) <= 10

def test_source_management(page: Page):
    """Test source management UI."""
    page.goto("http://localhost:5000/sources")

    # Wait for sources to load
    page.wait_for_selector(".source-card", timeout=5000)

    # Check that sources are displayed
    sources = page.locator(".source-card")
    count = sources.count()
    assert count > 0, "No sources displayed"

    # Test source status badge
    expect(sources.first.locator(".badge")).to_be_visible()

def test_api_health_check(page: Page):
    """Test health check endpoint."""
    response = page.request.get("http://localhost:5000/api/health")

    assert response.ok
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data

def test_mobile_responsive(page: Page):
    """Test mobile responsiveness."""
    # Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto("http://localhost:5000")

    # Check no horizontal scroll
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width == client_width, "Horizontal scroll detected on mobile"
```

Run tests:
```bash
pytest tests/test_ui_playwright.py --headed  # Run with visible browser
pytest tests/test_ui_playwright.py           # Run headless
```

---

## Recommendations

### Immediate Actions (Within 24 hours)
1. ✅ **CRITICAL**: Revoke all exposed API keys in .env file
2. ✅ **CRITICAL**: Fix event loop reuse issue in `run_async()`
3. ✅ **CRITICAL**: Fix SQLite thread safety with thread-local connections
4. ⚠️ **HIGH**: Implement async task management for background collection
5. ⚠️ **HIGH**: Replace `schedule` library with native asyncio scheduling

### Short Term (Within 1 week)
6. Add comprehensive error handling for all external API calls
7. Implement proper logging and monitoring
8. Add input validation for all API endpoints
9. Set up Playwright automated testing suite
10. Add database connection pooling and cleanup

### Long Term (Within 1 month)
11. Implement rate limiting and caching for external APIs
12. Add comprehensive unit and integration tests
13. Set up CI/CD pipeline with automated testing
14. Implement proper secrets management (e.g., HashiCorp Vault, AWS Secrets Manager)
15. Performance optimization with profiling and benchmarking

---

## Additional Notes

### Files Analyzed
- ✅ `run.py` - Entry point
- ✅ `src/app.py` - Flask application
- ✅ `src/config/settings.py` - Configuration
- ✅ `src/api/news_api.py` - API endpoints (1519 lines)
- ✅ `src/services/news_collector_service.py` - Collection service
- ✅ `src/services/sqlite_storage_service.py` - Database service
- ✅ `src/services/data_collection_service.py` - Data collection
- ✅ `src/processors/news_processor.py` - Content processing
- ✅ `src/collectors/rss_collector.py` - RSS collection
- ✅ `.env` - Environment configuration (SECURITY ISSUE!)

### Tools Used
- Manual code review
- Static analysis
- Playwright (installed in venv)
- Python syntax checking

### Documentation Updated
- ✅ Added virtual environment setup instructions to `CLAUDE.md`
- ✅ Added .env configuration guide to `CLAUDE.md`
- ✅ Added Playwright MCP testing section to `CLAUDE.md`

---

**Report Generated By:** Claude Code Analysis
**Date:** 2025-10-16
**Total Issues Found:** 15 (5 Critical, 6 High, 4 Medium)
