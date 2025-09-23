# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a News Agent application that automatically collects, processes, and analyzes news articles from various sources. It's built using Flask and integrates with OpenAI for content analysis, offering features like sentiment analysis, bias detection, and automatic summarization.

## Development Commands

### Running the Application
```bash
python run.py
```
The application starts on `http://localhost:5000` by default.

### Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp env.example .env
```

### Linting
```bash
# Based on CI configuration
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics
```

## Architecture

### Core Components

1. **Application Layer** (`src/app.py`): Flask web application with API endpoints and web interface
2. **Collectors** (`src/collectors/`): News collection from RSS feeds and other sources
3. **Processors** (`src/processors/`): Content analysis including sentiment and bias detection
4. **Services** (`src/services/`): Business logic coordination
5. **API Layer** (`src/api/`): RESTful API endpoints for news operations
6. **Models** (`src/models/`): Data models for news articles and collections
7. **Configuration** (`src/config/settings.py`): Environment-based configuration management

### Technology Stack

- **Backend**: Python 3.8+, Flask, asyncio
- **AI/ML**: OpenAI API, NLTK, TextBlob, Transformers, PyTorch
- **Data Processing**: pandas, NumPy
- **News Collection**: feedparser, newspaper3k, requests, BeautifulSoup
- **Database**: MongoDB (PyMongo), Redis
- **Web Scraping**: newspaper3k, requests
- **Social Media**: Tweepy (Twitter), PRAW (Reddit)
- **Visualization**: Plotly, Dash, Matplotlib, Seaborn
- **Frontend**: Bootstrap 5, Chart.js, jQuery

### Key Features

- Multi-source news collection (RSS, APIs, web scraping)
- AI-powered content analysis (sentiment, bias detection, 5W1H extraction)
- Automatic summarization and keyword extraction
- Real-time monitoring and statistics
- Web interface for management and visualization

## Configuration

The application uses environment variables for configuration. Copy `env.example` to `.env` and configure:

### Required API Keys
- `OPENAI_API_KEY`: For AI content analysis
- `NEWS_API_KEY`: For NewsAPI integration

### Optional Configuration
- Database: MongoDB URI, Redis URL
- Social Media: Twitter, Reddit API credentials
- Collection settings: intervals, limits, RSS feeds
- Application: Flask secret key, debug mode, logging level

## Data Flow

1. **Collection**: RSS feeds → RSSCollector → Raw articles
2. **Processing**: Raw articles → NewsProcessor → Analyzed articles
3. **Analysis**: Content → OpenAI/NLP → Sentiment/bias/summary
4. **Storage**: Processed articles → Database/Memory
5. **API/Web**: Data → Flask routes → JSON/HTML responses

## Entry Points

- `run.py`: Main application entry point
- `src/app.py`: Flask application factory
- `src/services/news_collector_service.py`: Background collection service

## Important Notes

- The codebase includes many backup files (backup_*.py) which are not part of the active codebase
- Main application logic is in the `src/` directory
- Configuration validation happens at startup
- Logging is configured to both console and file (`news_agent.log`)
- The application supports both synchronous and asynchronous operations