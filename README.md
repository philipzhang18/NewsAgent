# NewsAgent - AI News Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated AI news collection and analysis platform. Collects news from multiple sources, filters for AI-related content, and provides sentiment analysis, bias detection, and interactive visualizations.

## Features

- **AI-Focused Collection**: Automatically filters for AI/ML news across all sources
- **5 Data Sources**: NewsAPI, The Guardian API, NYTimes API, RSS feeds, Reddit
- **AI Analysis**: Sentiment analysis, bias detection, 5W1H extraction via Qwen/OpenAI-compatible LLM
- **Unified Dashboard**: Single-click collection with 7-day or 30-day range
- **Real-time Stats**: Per-source article counts, sentiment distribution, source charts
- **Bilingual UI**: English and Chinese interface

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd newsagent
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your API keys

# Run
python run.py
```

Open http://localhost:5000

## Configuration

Edit `.env` with your API keys:

```env
# LLM (OpenAI-compatible endpoint)
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=              # Leave empty for OpenAI, or set for compatible APIs

# News Sources
NEWS_API_KEY=your_key         # https://newsapi.org/register
GUARDIAN_API_KEY=your_key     # https://open-platform.theguardian.com/access/
NYTIMES_API_KEY=your_key      # https://developer.nytimes.com/get-started

# Social Media
REDDIT_CLIENT_ID=your_id      # https://www.reddit.com/prefs/apps
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=python:newsagent:v1.0
```

## Architecture

```
src/
├── api/            # REST API endpoints
├── collectors/     # News source collectors
│   ├── rss_collector.py
│   ├── newsapi_collector.py
│   ├── guardian_collector.py
│   ├── nytimes_collector.py
│   └── reddit_collector.py
├── processors/     # AI analysis (sentiment, bias, 5W1H)
├── services/       # Business logic & orchestration
├── models/         # Data models
├── templates/      # Web UI (Jinja2)
└── config/         # Settings
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/news/collect` | POST | Collect AI news (accepts `{"days": 7}` or `{"days": 30}`) |
| `/api/news/articles` | GET | Get articles (supports `?q=`, `?ai_only=true`, `?limit=`) |
| `/api/news/stats` | GET | Dashboard statistics |
| `/api/news/sources` | GET | Configured data sources |
| `/api/news/diagnostics` | GET | Source health diagnostics |
| `/api/news/ai-summary` | POST | Generate AI analysis summary |

## Data Sources

| Source | Type | What It Collects |
|--------|------|-----------------|
| NewsAPI | API | Global news from 80,000+ sources |
| The Guardian | API | Full-text articles with tags |
| NYTimes | API | Article search with keywords |
| RSS Feeds | RSS | BBC, Guardian, Al Jazeera, CNN |
| Reddit | Social | Posts from r/news, r/worldnews, r/technology |

## Development

```bash
# Lint
flake8 src/ --select=E9,F63,F7,F82 --exclude=__pycache__

# Test
pytest

# Test collectors
python scripts/test_collectors.py
```

## License

MIT
