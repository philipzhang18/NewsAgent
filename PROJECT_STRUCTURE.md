# News Agent — Project Structure (v2 SQLite)

## Active architecture

```
Flask (app.py)
  ├── /api/news/*     → news_api.py (articles, sources, collection, AI)
  ├── /api/visualization/* → visualization_api.py
  └── /dashboard/     → dash_app_enhanced.py

data_collection_service  → collectors → SQLite (data/news_articles.db)
NewsProcessor            → analysis after collection
```

## Key directories

| Path | Role |
|------|------|
| `src/app.py` | Flask app factory, lifecycle routes |
| `src/api/news_api.py` | Main REST API |
| `src/services/data_collection_service.py` | Multi-source collection orchestrator |
| `src/services/sqlite_storage_service.py` | SQLite + FTS5 persistence |
| `src/services/storage_service.py` | Unified storage API wrapper |
| `src/collectors/` | RSS, NewsAPI, Twitter, Reddit, Exa |
| `src/processors/news_processor.py` | Sentiment, summary, 5W1H |
| `src/static/js/i18n.js` | EN/中文 UI switching |
| `sources_config.json` | RSS source list |
| `scripts/test_collectors.py` | Live collector diagnostics |

## Removed / legacy

- MongoDB, Redis, Celery, Docker deployment stack
- `news_collector_service`, `cache_service`, `api_collector`, `web_scraper_collector`

See [docs/COLLECTOR_GUIDE.md](docs/COLLECTOR_GUIDE.md) for per-source setup and troubleshooting.
