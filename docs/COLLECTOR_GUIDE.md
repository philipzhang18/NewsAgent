# Data Source Collector Guide

This document describes each data source, required configuration, and troubleshooting.

## Quick test

```bash
python scripts/test_collectors.py
```

Or via API while the app is running:

- `GET /api/news/diagnostics` — test each source connection
- `POST /api/news/collect-all` — full collection + processing + SQLite save

## Sources

### RSS (BBC, Guardian, CNN, etc.)

| Requirement | `sources_config.json` RSS entries or `RSS_FEEDS` in `.env` |
| Common failures | Feed URL moved, TLS errors, empty feed |
| Fix | Update URL in Sources UI or `sources_config.json`; verify URL in browser |

### NewsAPI

| Requirement | `NEWS_API_KEY` in `.env` |
| Common failures | Invalid key (401), daily quota (429), dev plan limits |
| Fix | Register at https://newsapi.org — free tier has strict limits |

### Twitter / X

| Requirement | `TWITTER_BEARER_TOKEN` or full OAuth credentials in `.env` |
| Common failures | Invalid token (401/403), API tier does not allow search, rate limits |
| Fix | Create app at https://developer.x.com — Basic/Free tiers have very limited search |

### Reddit

| Requirement | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` |
| Common failures | Wrong user agent format, invalid credentials |
| Fix | Create "script" app at https://www.reddit.com/prefs/apps — user agent must identify your app |

### Exa AI Search

| Requirement | `EXA_API_KEY` in `.env` |
| Common failures | Invalid key (401), quota exceeded |
| Fix | Get key at https://exa.ai |

## Processing pipeline

After each `collect-all`:

1. Raw articles saved to SQLite (`data/news_articles.db`)
2. Each article processed (sentiment, summary, 5W1H when `OPENAI_API_KEY` set)
3. Processed article updated in database

Manual reprocess: `POST /api/news/process` or `POST /api/news/reprocess`

## Architecture (simplified)

```
UI → Flask API → data_collection_service → collectors → SQLite
                      ↓
              NewsProcessor (analysis)
```

No MongoDB, Redis, or Celery required for local operation.
