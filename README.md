# 📰 News Agent

News Agent is an intelligent news processing agent that automatically collects, filters, summarizes, and analyzes news information. It leverages large language models (LLMs) and knowledge graphs to help news professionals and content creators efficiently acquire and process news content.

News Agent 是一个面向新闻专业的智能代理 (Agent)，用于自动化新闻采集、信息筛选、摘要生成和舆情分析。它结合了大语言模型 (LLM) 与新闻领域知识，帮助新闻从业者更高效地获取和处理资讯。

---

## ✨ Key Features / 功能特点

- **Multi-source Collection / 新闻检索**: Collects real-time news from multiple news websites, RSS feeds, and social media APIs / 从多渠道（新闻网站、RSS、社交媒体 API）获取实时新闻
- **Information Extraction / 信息抽取**: Extracts key news elements (5W1H: Who, What, When, Where, Why, How) / 提取新闻核心要素（5W1H：Who, What, When, Where, Why, How）
- **Automatic Summarization / 摘要生成**: Generates news summaries with support for long-form compression / 自动生成新闻摘要，支持长文压缩
- **Source Verification / 多源比对**: Compares multiple media reports on the same event to identify discrepancies / 对同一事件的多家媒体报道进行比对，识别差异
- **Sentiment Analysis / 舆情分析**: Analyzes public sentiment on social platforms and trending topics / 分析社交平台上的相关评论与情绪趋势
- **Bias Detection / 新闻伦理提醒**: Identifies potential bias, exaggeration, or unreliable sources / 在输出中提示可能的偏见、虚假或不当引用

---

## 📦 Installation / 安装

```bash
# Clone repository / 克隆仓库
git clone https://github.com/philipzhang18/NewsAgent.git
cd NewsAgent

# Create virtual environment (recommended) / 建立虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

# Install dependencies / 安装依赖
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in your API keys and configuration settings
3. Run the application

## Usage

```bash
# Start the news collection service
python src/services/news_collector.py

# Start the web interface
python src/app.py

# Run analysis tasks
python src/analysis/news_analyzer.py
```

## Project Structure

```
NewsAgent/
├── src/
│   ├── collectors/      # News collection modules
│   ├── processors/      # Text processing and analysis
│   ├── services/        # Core services
│   ├── api/            # API endpoints
│   ├── models/         # Data models
│   └── utils/          # Utility functions
├── data/               # Data storage
├── config/             # Configuration files
├── tests/              # Test files
└── docs/               # Documentation
```

## License

MIT License