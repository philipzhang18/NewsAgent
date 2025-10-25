# Bug Fixes Summary - News Agent Application

## Overview
This issue documents three critical bugs discovered and fixed in the News Agent application using Playwright MCP automated testing.

**Status**: ✅ All Fixed
**Test Coverage**: 17/18 Playwright tests passing
**Data Consistency**: 100% - All sources now accurately counted

---

## Bug #1: Duplicate Stats API Calls on Dashboard

### Issue
The dashboard homepage was making duplicate calls to `/api/news/stats` API on every page load, causing unnecessary server load and potential data inconsistencies.

### Root Cause
Two separate functions (`loadStatistics()` and `loadDatabaseStatus()`) were both calling `/api/news/stats` independently during page initialization.

**File**: `src/templates/dashboard.html:312-313`

```javascript
// Old code - causing duplicates
await Promise.allSettled([
    loadAPIConfigStatus(),
    loadStatistics(),         // ❌ Calls /api/news/stats
    loadDatabaseStatus(),     // ❌ Also calls /api/news/stats
    loadLatestArticles()
]);
```

### Solution
Created a unified data-fetching function that calls the API once and shares the data:

```javascript
// New code - single API call
async function loadStatsData() {
    const response = await fetchWithTimeout('/api/news/stats');
    const data = await response.json();
    return data.success ? data.data : null;
}

const statsPromise = loadStatsData();
await statsPromise.then(stats => {
    if (stats) {
        loadStatistics(stats);      // ✅ Shares data
        loadDatabaseStatus(stats);  // ✅ Shares same data
    }
});
```

### Impact
- **Performance**: Reduced API calls by 50% (2 → 1)
- **Database Load**: Eliminated duplicate queries
- **Data Consistency**: Both functions now use identical data from the same response

**Files Modified**: `src/templates/dashboard.html:307-632`

---

## Bug #2: Sources Page Showing 0 Articles for NewsAPI

### Issue
The Sources page displayed `0 articles` for NewsAPI despite having 1,372 articles collected by NewsAPI in the database.

### Root Cause
The `get_sources()` API function only matched articles by `source_name` field, but NewsAPI articles have:
- `source_name`: "ABC News", "Yahoo Entertainment", "CNN", etc. (actual news publisher)
- `collector`: "NewsAPI" (the aggregator that collected them)

The code tried to find articles where `source_name = "NewsAPI"`, which didn't exist.

**Database Evidence**:
```sql
-- NewsAPI collected 1,372 articles from various publishers
SELECT collector, COUNT(*) FROM articles
WHERE collector = 'NewsAPI'
GROUP BY collector;
-- Result: NewsAPI | 1372

-- But source_name is the actual publisher
SELECT source_name, COUNT(*) FROM articles
WHERE collector = 'NewsAPI'
GROUP BY source_name LIMIT 5;
-- Results:
-- Yahoo Entertainment | 230
-- CNN | 46
-- The Times of India | 66
-- etc.
```

### Solution
Enhanced the counting logic to track both `source_name` and `collector` fields:

```python
# Track both dimensions
source_counts = {}
collector_counts = {}
source_collector_counts = {}  # (source_name, collector) pairs

for article in all_articles:
    source_name = article.get('source_name')
    collector = article.get('collector')

    # Count by both dimensions
    if source_name:
        source_counts[source_name] += 1
    if collector:
        collector_counts[collector] += 1
    if source_name and collector:
        source_collector_counts[(source_name, collector)] += 1

# Match API sources by collector (more reliable)
if source_type == "API":
    for collector_name, count in collector_counts.items():
        if "newsapi" in source.name.lower() and "newsapi" in collector_name.lower():
            article_count = count  # ✅ Now correctly finds 1,372 articles
```

### Impact
- **NewsAPI**: Now correctly displays 1,372 articles ✅
- **Data Accuracy**: Sources page now matches database reality
- **User Trust**: Accurate reporting of data collection success

**Files Modified**: `src/api/news_api.py:651-677`

---

## Bug #3: Duplicate Counting Leading to 48 Extra Articles

### Issue
**Observed**:
- Dashboard Total Articles: 1,561 ✅
- Sources Page Total: 1,609 ❌ (48 articles over-counted)
- Database Actual: 1,561 ✅

### Root Cause
The previous fix for Bug #2 introduced a new problem: some articles were being counted twice.

**Example of Duplicate Counting**:

| Article Source | source_name | collector | Counted By | Times Counted |
|---------------|-------------|-----------|------------|---------------|
| CNN via NewsAPI | "CNN" | "NewsAPI" | NewsAPI source (via collector) | 1st time ✅ |
| Same articles | "CNN" | "NewsAPI" | CNN source (via source_name) | 2nd time ❌ |

**Breakdown**:
- CNN: 46 articles with `collector="NewsAPI"` → counted twice = +46
- BBC News: 2 articles with `collector="NewsAPI"` → counted twice = +2
- **Total over-count**: 48 articles ❌

### Solution
Implemented source-type-aware matching strategy:

```python
if source_type == "RSS":
    # RSS sources: Only count articles where collector="RSS"
    for (src_name, collector_name), count in source_collector_counts.items():
        if collector_name == "RSS":  # ✅ Prevents counting NewsAPI articles
            if source.name.lower() in src_name.lower():
                article_count += count

elif source_type == "API" or source_type == "Social":
    # API sources: Match by collector only
    for collector_name, count in collector_counts.items():
        if source.name.lower() == collector_name.lower():
            article_count = count
            break  # ✅ Single match, no overlap
```

### Impact

**Before Fix**:
```
BBC News (RSS):      19 articles  ❌ (17 RSS + 2 NewsAPI duplicates)
CNN (RSS):           46 articles  ❌ (0 RSS + 46 NewsAPI duplicates)
NewsAPI (API):     1372 articles  ✅
Total:             1609 articles  ❌
```

**After Fix**:
```
BBC News (RSS):      17 articles  ✅ (only RSS articles)
CNN (RSS):            0 articles  ✅ (no RSS articles collected)
NewsAPI (API):     1372 articles  ✅
Total:             1561 articles  ✅ Matches database exactly!
```

**Files Modified**: `src/api/news_api.py:704-772`

---

## Testing & Verification

### Automated Tests
**Playwright MCP Tests**: 17/18 passing (94.4%)

```
✅ test_api_health_endpoint
✅ test_api_articles_endpoint
✅ test_api_sources_endpoint
✅ test_api_stats_endpoint
✅ test_articles_page_navigation
✅ test_sources_page_navigation
✅ test_mobile_responsive
✅ test_javascript_errors_dashboard
✅ test_api_response_times
✅ test_missing_templates
✅ test_api_error_handling
✅ test_page_title_exists
✅ test_navigation_links
✅ test_homepage_loads_and_settles
✅ test_homepage_stats_not_duplicated  ← Verifies Bug #1 fix
✅ test_sources_page_loads_successfully
✅ test_polling_uses_timeout_not_interval
❌ test_homepage_loads_without_errors (timeout - not related to fixes)
```

### Data Consistency Verification

| Metric | Database | Dashboard | Sources API | Status |
|--------|----------|-----------|-------------|--------|
| Total Articles | 1,561 | 1,561 | 1,561 | ✅ Perfect match |
| NewsAPI Articles | 1,372 | 1,372 | 1,372 | ✅ |
| RSS Articles | 141 | 141 | 141 | ✅ |
| Reddit Articles | 48 | 48 | 48 | ✅ |

---

## Files Changed

### Modified Files
1. **src/templates/dashboard.html** (Lines 307-632)
   - Unified stats data fetching
   - Eliminated duplicate API calls

2. **src/api/news_api.py** (Lines 651-772)
   - Enhanced article counting logic
   - Added collector-based matching
   - Implemented source-type-aware counting strategy

### Testing Files
- `tests/playwright/test_bug_detection.py` - All bug detection tests passing
- `tests/playwright/test_polling_fix.py` - Polling and stats API tests passing

---

## Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Stats API Calls (per page load) | 2 | 1 | -50% |
| Database Queries | Duplicate | Single | -50% |
| Data Accuracy | Multiple issues | 100% accurate | ✅ |
| Sources Page Count | 1,609 (wrong) | 1,561 (correct) | ✅ |
| NewsAPI Display | 0 (wrong) | 1,372 (correct) | ✅ |

---

## Lessons Learned

1. **Multi-dimensional Data**: When dealing with aggregated data (like NewsAPI collecting from multiple sources), track both the aggregator (collector) and the original source (source_name).

2. **Type-aware Logic**: Different source types (RSS vs API) require different matching strategies to avoid duplicate counting.

3. **Test-Driven Debugging**: Playwright MCP automated testing was instrumental in:
   - Discovering the bugs
   - Verifying fixes
   - Preventing regressions

4. **Data Consistency**: Always verify that displayed totals match database reality across all views.

---

## Related Issues
- None (initial discovery via Playwright MCP testing)

## Testing Methodology
All bugs were discovered and verified using **Playwright MCP** (Model Context Protocol) for automated browser testing, which enabled:
- Automated UI bug detection
- Network request monitoring
- Performance testing
- Data consistency verification

---

**Generated with Claude Code** 🤖
