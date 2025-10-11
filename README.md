# 📰 NewsAgent - AI-Powered News Intelligence Platform

<div align="center">

**Intelligent News Collection, Analysis & Visualization Platform**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()

[Features](#features) • [Quick Start](#quick-start) • [Documentation](#documentation) • [API](#api-reference) • [Deployment](#deployment)

</div>

---

## 🌟 Overview

NewsAgent is an enterprise-grade news intelligence platform that automatically collects, processes, and analyzes news from multiple sources using AI and machine learning. It provides real-time insights, sentiment analysis, bias detection, and interactive visualizations.

### Key Highlights

- 🤖 **AI-Powered Analysis**: OpenAI GPT integration for intelligent content processing
- 📊 **Interactive Dashboard**: Real-time data visualization with Plotly/Dash
- 🔍 **Smart Search**: Intelligent search with sentiment and keyword filtering
- 🌐 **Multi-Source Collection**: RSS, APIs, Twitter, Reddit, web scraping
- ⚡ **Async Processing**: Celery task queue for background operations
- 🔒 **Enterprise Security**: HTTPS, CORS, rate limiting, API authentication
- 📈 **Monitoring & Alerts**: Comprehensive health checks and metrics
- 💾 **Data Protection**: Automated backup and recovery system
- 🐳 **Docker Ready**: Full containerization support

---

## ✨ Features

### News Collection
- **Multi-Source Support**: RSS feeds, NewsAPI, Twitter/X, Reddit, web scraping
- **Automatic Scheduling**: Configurable collection intervals with Celery
- **Smart Caching**: Redis-based caching to reduce API calls
- **Error Handling**: Robust retry logic and graceful degradation

### AI-Powered Processing
- **Sentiment Analysis**: Emotional tone detection (positive/neutral/negative)
- **Bias Detection**: Political and editorial bias identification
- **5W1H Extraction**: Who, What, When, Where, Why, How analysis
- **Auto-Summarization**: Intelligent content summarization
- **Keyword Extraction**: Automatic keyword and entity recognition

### Data Visualization
- **Real-Time Dashboard**: Interactive charts and graphs
- **Sentiment Timeline**: Trend analysis over time
- **Source Analytics**: Article distribution by source
- **Keyword Cloud**: Most frequent topics and terms
- **Custom Reports**: Export and share insights

### Search & Filter
- **Intelligent Search**: Full-text search across titles, content, keywords
- **Advanced Filters**: By sentiment, source, date range, keywords
- **Saved Searches**: Bookmark and reuse search queries
- **Export Results**: CSV, JSON, PDF formats

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Redis Server (optional, for caching)
- MongoDB (optional, for persistence)
- OpenAI API Key
- NewsAPI Key

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd newsagent

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp env.example .env
# Edit .env with your API keys

# 5. Run application
python run.py
```

### Access the Application

- **Main Application**: http://localhost:5000
- **Interactive Dashboard**: http://localhost:5000/dashboard/
- **Health Check**: http://localhost:5000/api/health

---

## 📖 Documentation

### Core Documentation

- [**Deployment Guide**](docs/DEPLOYMENT_GUIDE.md) - Production deployment with Nginx/Gunicorn
- [**Celery Usage**](docs/CELERY_USAGE.md) - Async task queue configuration
- [**Visualization Guide**](docs/VISUALIZATION_GUIDE.md) - Dashboard and charts
- [**HTTPS & CORS**](docs/HTTPS_CORS_GUIDE.md) - Security configuration
- [**Backup & Recovery**](docs/BACKUP_RECOVERY_GUIDE.md) - Data protection

### Additional Resources

- [Architecture Overview](PROJECT_STRUCTURE.md)
- [Startup Guide](STARTUP.md)

---

## 🔧 Configuration

### Environment Variables

```env
# API Keys (Required)
OPENAI_API_KEY=your_openai_key
NEWS_API_KEY=your_newsapi_key

# Application
FLASK_SECRET_KEY=your_secret_key
DEBUG=True
LOG_LEVEL=INFO

# Database (Optional)
MONGODB_URI=mongodb://localhost:27017/news_agent
REDIS_URL=redis://localhost:6379

# Celery (Optional)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

---

## 🎯 Usage Examples

### Start Services

```bash
# Start main application
python run.py

# Start Celery workers (optional, separate terminal)
celery -A src.celery_app:celery_app worker -Q collection,processing -l info

# Start Celery beat scheduler (optional)
celery -A src.celery_app:celery_app beat -l info
```

### API Usage

```python
import requests

# Get latest articles
response = requests.get('http://localhost:5000/api/news/articles?limit=10')
articles = response.json()

# Trigger manual collection
response = requests.post('http://localhost:5000/api/news/collect')

# Get statistics
response = requests.get('http://localhost:5000/api/news/stats')
stats = response.json()
```

---

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services included: app, workers, mongodb, redis, nginx

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────┐
│                 Web Interface                   │
│           (Flask + Bootstrap + Dash)            │
├─────────────────────────────────────────────────┤
│                  API Layer                      │
│         (RESTful + WebSocket Support)           │
├─────────────────────────────────────────────────┤
│              Service Layer                      │
│   NewsCollector │ Processor │ Monitoring       │
├─────────────────────────────────────────────────┤
│            Background Tasks                     │
│        (Celery + Redis Message Queue)          │
├─────────────────────────────────────────────────┤
│              Data Storage                       │
│        MongoDB │ Redis │ File System           │
└─────────────────────────────────────────────────┘
```

---

## 🔐 Security

### Implemented Features

- ✅ **HTTPS Support**: SSL/TLS encryption
- ✅ **CORS Configuration**: Cross-origin control
- ✅ **Rate Limiting**: API throttling
- ✅ **API Authentication**: Secure access
- ✅ **Input Validation**: Data sanitization
- ✅ **Secret Management**: Environment config

---

## 📈 Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:5000/api/health

# Detailed monitoring
curl http://localhost:5000/api/monitoring/health

# System metrics
curl http://localhost:5000/api/monitoring/metrics
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test
pytest tests/test_cache_service.py
```

---

## 🛠️ Development

### Project Structure

```
newsagent/
├── src/              # Source code
│   ├── api/          # API endpoints
│   ├── collectors/   # News collectors
│   ├── processors/   # Content processing
│   ├── services/     # Business logic
│   └── models/       # Data models
├── tests/            # Test suite
├── config/           # Configurations
├── scripts/          # Utility scripts
└── docs/             # Documentation
```

---

## 📝 License

This project is licensed under the MIT License.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/newsagent/issues)
- **Documentation**: See `/docs` folder

---

<div align="center">

Made with ❤️ by the NewsAgent Team

</div>
