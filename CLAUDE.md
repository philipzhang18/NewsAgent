# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a News Agent application that automatically collects, processes, and analyzes news articles from various sources. It's built using Flask and integrates with OpenAI for content analysis, offering features like sentiment analysis, bias detection, and automatic summarization.

## Development Commands

### Environment Setup (Required First Step)

**IMPORTANT**: Always work within the virtual environment to ensure proper dependency isolation and avoid conflicts.

#### 1. Create Virtual Environment
```bash
# Create virtual environment in project root
python -m venv venv
# OR use .venv (recommended for better IDE support)
python -m venv .venv
```

#### 2. Activate Virtual Environment

**Windows:**
```bash
# Using venv
venv\Scripts\activate

# Using .venv
.venv\Scripts\activate

# You should see (venv) or (.venv) prefix in your terminal
```

**Linux/macOS:**
```bash
# Using venv
source venv/bin/activate

# Using .venv
source .venv/bin/activate

# You should see (venv) or (.venv) prefix in your terminal
```

#### 3. Install Dependencies
```bash
# Ensure you are in the virtual environment first!
pip install -r requirements.txt

# Verify installation
pip list
```

#### 4. Configure Environment Variables (.env)

**Copy the example configuration:**
```bash
# Windows
copy env.example .env

# Linux/macOS
cp env.example .env
```

**Edit .env file with your API keys and configuration:**
```env
# Required API Keys
OPENAI_API_KEY=your_actual_openai_api_key_here
NEWS_API_KEY=your_actual_newsapi_key_here

# Optional API Keys (for additional sources)
GUARDIAN_API_KEY=your_guardian_key
NYTIMES_API_KEY=your_nytimes_key
TWITTER_BEARER_TOKEN=your_twitter_token
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret

# Application Settings
FLASK_SECRET_KEY=generate_a_random_secret_key
DEBUG=True
LOG_LEVEL=INFO

# Database (Optional)
MONGODB_URI=mongodb://localhost:27017/news_agent
REDIS_URL=redis://localhost:6379
```

**Important Notes:**
- Never commit `.env` file to version control (already in .gitignore)
- Generate a strong FLASK_SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
- Obtain API keys from:
  - OpenAI: https://platform.openai.com/api-keys
  - NewsAPI: https://newsapi.org/register
  - Guardian: https://open-platform.theguardian.com/access/
  - NYTimes: https://developer.nytimes.com/get-started

### Running the Application

**ALWAYS run the application inside the virtual environment:**

```bash
# 1. Ensure virtual environment is activated
# You should see (venv) or (.venv) in your terminal

# 2. Run the application
python run.py

# The application will start on http://localhost:5000
```

**Expected Output:**
```
INFO - Starting News Agent application...
INFO - Debug mode: True
INFO - Log level: INFO
* Running on http://0.0.0.0:5000
```

**If you see configuration errors:**
```
ERROR - Invalid configuration. Please check your environment variables.
ERROR - Required: OPENAI_API_KEY, NEWS_API_KEY
```
This means you need to properly configure your `.env` file with valid API keys.

### Linting
```bash
# Install flake8 in virtual environment if not already installed
pip install flake8

# Run critical error checks
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv,.venv,backup_*

# Run code quality checks
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics --exclude=venv,.venv,backup_*
```

### Testing with Playwright MCP (Automated UI Testing)

**Playwright MCP** is a Model Context Protocol server that provides browser automation for testing web applications.

#### Prerequisites for Playwright MCP

1. **Ensure virtual environment is activated**
2. **Install Playwright MCP dependencies:**
```bash
# Install MCP server for Playwright
npm install -g @playwright/test

# Install Playwright browsers
npx playwright install
```

#### Using Playwright MCP to Check for Bugs

**1. Start the application first:**
```bash
# In terminal 1: Start the Flask app
python run.py
```

**2. Run Playwright tests:**
```bash
# In terminal 2: Run automated browser tests
# Test homepage accessibility
npx playwright test --headed

# Or use specific test files if you have them
npx playwright test tests/e2e/
```

#### Common Issues to Check with Playwright MCP:

- **Homepage Loading**: Verify page loads without errors
- **Navigation**: Test all menu links and navigation flows
- **Forms**: Test article collection, search functionality
- **API Endpoints**: Verify AJAX calls complete successfully
- **Mobile Responsiveness**: Test on different viewport sizes
- **JavaScript Errors**: Check browser console for errors
- **Performance**: Measure page load times
- **Accessibility**: Check ARIA labels and keyboard navigation

#### Manual Bug Checking (Without MCP)

If Playwright MCP is not available, perform manual checks:

```bash
# Check Python syntax errors
python -m py_compile src/**/*.py

# Check for common issues
python -m pylint src/ --disable=all --enable=E,F

# Run the application with debug mode
DEBUG=True python run.py

# Monitor logs for errors
tail -f news_agent.log
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