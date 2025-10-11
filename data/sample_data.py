# Sample news data for testing and demonstration

SAMPLE_ARTICLES = [
    {
        "id": "sample_001",
        "title": "AI Breakthrough: New Language Model Achieves Human-Level Understanding",
        "content": "Researchers at leading tech companies have developed a new artificial intelligence system that demonstrates human-level comprehension across multiple domains. The model shows remarkable ability in understanding context, nuance, and complex reasoning tasks.",
        "url": "https://example.com/ai-breakthrough",
        "source_name": "TechNews Daily",
        "author": "Jane Smith",
        "published_at": "2024-01-15T10:30:00Z",
        "collected_at": "2024-01-15T11:00:00Z",
        "category": "Technology",
        "keywords": ["AI", "Machine Learning", "Natural Language Processing", "Research"],
        "sentiment": "positive",
        "sentiment_score": 0.75,
        "bias_score": 0.1,
        "is_processed": True,
        "summary": "A new AI model demonstrates human-level understanding across multiple domains, showing advancement in comprehension and reasoning capabilities."
    },
    {
        "id": "sample_002",
        "title": "Global Climate Summit Reaches Historic Agreement",
        "content": "World leaders have agreed on unprecedented measures to combat climate change at the annual climate summit. The agreement includes binding emissions targets and substantial funding for renewable energy infrastructure in developing nations.",
        "url": "https://example.com/climate-summit",
        "source_name": "Global News Network",
        "author": "John Doe",
        "published_at": "2024-01-15T14:20:00Z",
        "collected_at": "2024-01-15T14:30:00Z",
        "category": "Environment",
        "keywords": ["Climate Change", "Environment", "Policy", "International Relations"],
        "sentiment": "positive",
        "sentiment_score": 0.65,
        "bias_score": 0.05,
        "is_processed": True,
        "summary": "World leaders reach historic climate agreement with binding emissions targets and renewable energy funding."
    },
    {
        "id": "sample_003",
        "title": "Stock Markets Face Volatility Amid Economic Concerns",
        "content": "Major stock indices experienced significant fluctuations today as investors react to mixed economic signals. Analysts point to inflation concerns and geopolitical tensions as primary factors driving market uncertainty.",
        "url": "https://example.com/market-volatility",
        "source_name": "Financial Times",
        "author": "Sarah Johnson",
        "published_at": "2024-01-15T16:45:00Z",
        "collected_at": "2024-01-15T17:00:00Z",
        "category": "Business",
        "keywords": ["Stock Market", "Economy", "Finance", "Investment"],
        "sentiment": "negative",
        "sentiment_score": -0.55,
        "bias_score": 0.15,
        "is_processed": True,
        "summary": "Stock markets show volatility due to inflation concerns and geopolitical tensions affecting investor confidence."
    },
    {
        "id": "sample_004",
        "title": "New Study Reveals Benefits of Mediterranean Diet",
        "content": "A comprehensive 10-year study involving thousands of participants has confirmed the significant health benefits of the Mediterranean diet. Researchers found reduced risk of cardiovascular disease, diabetes, and improved cognitive function among adherents.",
        "url": "https://example.com/mediterranean-diet",
        "source_name": "Health Science Review",
        "author": "Dr. Michael Chen",
        "published_at": "2024-01-14T09:15:00Z",
        "collected_at": "2024-01-14T09:30:00Z",
        "category": "Health",
        "keywords": ["Health", "Nutrition", "Research", "Mediterranean Diet"],
        "sentiment": "positive",
        "sentiment_score": 0.70,
        "bias_score": 0.02,
        "is_processed": True,
        "summary": "10-year study confirms Mediterranean diet reduces cardiovascular risk and improves cognitive function."
    },
    {
        "id": "sample_005",
        "title": "Tech Giant Announces Major Layoffs Amid Restructuring",
        "content": "One of the world's largest technology companies announced plans to reduce its workforce by 15% as part of a major restructuring effort. The decision comes as the company shifts focus to artificial intelligence and cloud computing services.",
        "url": "https://example.com/tech-layoffs",
        "source_name": "Business Insider",
        "author": "Emily Rodriguez",
        "published_at": "2024-01-14T13:00:00Z",
        "collected_at": "2024-01-14T13:15:00Z",
        "category": "Technology",
        "keywords": ["Technology", "Employment", "Business", "AI", "Cloud Computing"],
        "sentiment": "negative",
        "sentiment_score": -0.60,
        "bias_score": 0.12,
        "is_processed": True,
        "summary": "Major tech company cutting 15% of workforce in restructuring to focus on AI and cloud services."
    }
]

SAMPLE_SOURCES = [
    {
        "id": "sample_source_001",
        "name": "TechNews Daily",
        "type": "rss",
        "url": "https://example.com/technews/feed",
        "category": "Technology",
        "is_active": True,
        "reliability_score": 0.85
    },
    {
        "id": "sample_source_002",
        "name": "Global News Network",
        "type": "api",
        "url": "https://api.example.com/news",
        "category": "General",
        "is_active": True,
        "reliability_score": 0.90
    },
    {
        "id": "sample_source_003",
        "name": "Financial Times",
        "type": "rss",
        "url": "https://example.com/ft/feed",
        "category": "Business",
        "is_active": True,
        "reliability_score": 0.92
    }
]
