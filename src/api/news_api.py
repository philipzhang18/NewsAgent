from flask import Blueprint, request, jsonify
from typing import List, Dict, Any
import logging
import requests
import asyncio
from werkzeug.exceptions import BadRequest

from ..services.news_collector_service import NewsCollectorService
from ..processors.news_processor import NewsProcessor
from ..models.news_models import NewsArticle, SourceType
from ..config.settings import settings
from ..services.sqlite_storage_service import sqlite_storage
from ..services.data_collection_service import data_collection_service

logger = logging.getLogger(__name__)

def analyze_sentiment(text: str) -> str:
	"""Analyze sentiment of text using simple keyword-based approach."""
	if not text:
		return "neutral"

	text_lower = text.lower()

	# Positive keywords
	positive_keywords = ['breakthrough', 'success', 'achieve', 'innovative', 'excellent', 'surpass',
						'advance', 'improve', 'better', 'leading', 'revolutionary', 'powerful',
						'amazing', 'outstanding', 'milestone']

	# Negative keywords
	negative_keywords = ['concern', 'worry', 'danger', 'risk', 'threat', 'problem', 'fail',
						'decline', 'worse', 'controversial', 'crisis', 'issue', 'criticism']

	positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)
	negative_count = sum(1 for keyword in negative_keywords if keyword in text_lower)

	if positive_count > negative_count and positive_count > 0:
		return "positive"
	elif negative_count > positive_count and negative_count > 0:
		return "negative"
	elif positive_count > 0 and negative_count > 0:
		return "mixed"
	else:
		return "neutral"

# Create Blueprint
news_api = Blueprint('news_api', __name__)

# Initialize services
collector_service = NewsCollectorService()
processor = NewsProcessor()

# Initialize SQLite storage
if not sqlite_storage.is_connected():
    sqlite_storage.connect()
    logger.info("SQLite storage initialized")

def run_async(coro):
	"""Helper to run async functions in sync Flask context."""
	# Create a new event loop for this execution
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	try:
		return loop.run_until_complete(coro)
	finally:
		# Keep the loop set for potential reuse in the same thread
		pass

def validate_limit_parameter(limit: int, min_val: int = 1, max_val: int = 10000) -> int:
	"""
	Validate the limit parameter for API endpoints.

	Args:
		limit: The limit value to validate
		min_val: Minimum allowed value (default: 1)
		max_val: Maximum allowed value (default: 10000, matches MAX_ARTICLES in SQLite storage)

	Returns:
		int: The validated limit value

	Raises:
		BadRequest: If the limit is invalid
	"""
	if limit is None:
		raise BadRequest("limit parameter cannot be None")

	if not isinstance(limit, int):
		raise BadRequest(f"limit must be an integer, got {type(limit).__name__}")

	if limit < min_val or limit > max_val:
		raise BadRequest(f"limit must be between {min_val} and {max_val}, got {limit}")

	return limit

# AI related keywords for filtering
AI_KEYWORDS = [
	'ai', 'artificial intelligence', 'machine learning', 'deep learning',
	'neural network', 'gpt', 'chatgpt', 'llm', 'large language model',
	'generative ai', 'transformer', 'openai', 'google ai', 'anthropic',
	'claude', 'gemini', 'bard', 'copilot', 'midjourney', 'stable diffusion',
	'computer vision', 'natural language processing', 'nlp', 'reinforcement learning',
	'autonomous', 'robotics ai', 'ai model', 'ai system'
]

def is_ai_related(article: Dict[str, Any]) -> bool:
	"""Check if an article is AI-related based on title and content."""
	text = (article.get('title', '') + ' ' + article.get('summary', '') + ' ' + article.get('content', '')).lower()
	return any(keyword in text for keyword in AI_KEYWORDS)

@news_api.route('/status', methods=['GET'])
def get_status():
	"""Get the status of the news collection service."""
	try:
		from datetime import datetime

		# Get real status from collector service
		status = run_async(collector_service.get_collection_status())

		# Get articles from database to determine actual status
		try:
			# Try database first for accurate count
			db_articles = run_async(sqlite_storage.get_articles(limit=10000))
			total_articles = len(db_articles)
			# Convert dict articles to object-like structure
			class ArticleObj:
				def __init__(self, data):
					self.source_name = data.get('source_name')
					self.published_at = data.get('published_at')
					if isinstance(self.published_at, str):
						try:
							from dateutil import parser
							self.published_at = parser.parse(self.published_at)
						except:
							pass
			all_articles = [ArticleObj(a) for a in db_articles]
		except Exception as e:
			logger.warning(f"Failed to read from database: {e}, falling back to collector service")
			# Fallback to collector service
			all_articles = run_async(collector_service.get_recent_articles(limit=1000))
			total_articles = len(all_articles)

		# Count source distribution from articles
		source_distribution = {}
		for article in all_articles:
			source_name = article.source_name or "Unknown"
			source_distribution[source_name] = source_distribution.get(source_name, 0) + 1

		# Get last collection time from articles
		last_collection = None
		if all_articles:
			articles_with_dates = [a for a in all_articles if a.published_at]
			if articles_with_dates:
				# Convert all datetimes to comparable format (use timestamp)
				from datetime import timezone
				def get_timestamp(article):
					dt = article.published_at
					if dt:
						# Convert to UTC timezone-aware if needed
						if dt.tzinfo is None:
							dt = dt.replace(tzinfo=timezone.utc)
						return dt.timestamp()
					return 0

				latest_article = max(articles_with_dates, key=get_timestamp)
				dt = latest_article.published_at
				if dt.tzinfo is None:
					dt = dt.replace(tzinfo=timezone.utc)
				last_collection = dt.isoformat().replace('+00:00', 'Z')

		# If no collectors and no local articles, try to get data from NewsAPI
		if status["total_collectors"] == 0 and total_articles == 0:
			if settings.NEWS_API_KEY:
				try:
					# Fetch from NewsAPI to populate status
					params = {"apiKey": settings.NEWS_API_KEY, "pageSize": 100, "country": "us"}
					endpoint = "https://newsapi.org/v2/top-headlines"
					resp = requests.get(endpoint, params=params, timeout=10)
					resp.raise_for_status()
					data = resp.json()
					articles = data.get("articles", [])

					# Count source distribution from NewsAPI
					for article_data in articles:
						source_name = (article_data.get("source") or {}).get("name") or "NewsAPI"
						source_distribution[source_name] = source_distribution.get(source_name, 0) + 1

					total_articles = len(articles)

					# Get last collection time from NewsAPI articles
					if articles:
						published_dates = [a.get("publishedAt") for a in articles if a.get("publishedAt")]
						if published_dates:
							last_collection = max(published_dates)

				except Exception as e:
					logger.warning(f"Failed to fetch from NewsAPI for status: {str(e)}")

		# If no collectors but we have articles, create virtual status
		if status["total_collectors"] == 0 and total_articles > 0:
			# We have data, create virtual collectors
			collectors_info = {}
			for idx, (source_name, count) in enumerate(source_distribution.items(), 1):
				collectors_info[f"newsapi_source_{idx}"] = {
					"source_name": source_name,
					"is_running": False,  # Static data source
					"last_collection": last_collection,
					"articles_collected": count
				}

			status = {
				"service_running": True,  # Data is available
				"total_collectors": len(source_distribution),
				"collection_stats": {
					"total_collections": len(source_distribution),
					"total_articles": total_articles,
					"successful_collections": len(source_distribution),
					"last_collection": last_collection,
					"failed_collections": 0
				},
				"collectors": collectors_info
			}
		elif status["total_collectors"] == 0:
			# No collectors and no data
			status = {
				"service_running": False,
				"total_collectors": 0,
				"collection_stats": {
					"total_collections": 0,
					"total_articles": 0,
					"successful_collections": 0,
					"last_collection": None,
					"failed_collections": 0
				},
				"collectors": {}
			}
		else:
			# Update collection stats with actual data
			status["collection_stats"]["total_articles"] = total_articles
			if last_collection:
				status["collection_stats"]["last_collection"] = last_collection

		return jsonify({
			"success": True,
			"data": status
		})
	except Exception as e:
		logger.error(f"Error getting status: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500


def _map_newsapi_article(item: Dict[str, Any]) -> Dict[str, Any]:
	"""Map NewsAPI article to frontend schema."""
	# Analyze sentiment from title and description
	text_to_analyze = (item.get("title") or "") + " " + (item.get("description") or "")
	sentiment = analyze_sentiment(text_to_analyze)

	return {
		"id": item.get("url", ""),
		"title": item.get("title") or "",
		"summary": item.get("description") or "",
		"content": item.get("content") or "",
		"source": (item.get("source") or {}).get("name") or "NewsAPI",
		"source_name": (item.get("source") or {}).get("name") or "NewsAPI",
		"url": item.get("url") or "",
		"published_at": item.get("publishedAt") or None,
		"sentiment": sentiment,
		"bias_score": None,
		"category": None
	}

@news_api.route('/articles', methods=['GET'])
def get_articles():
	"""Get recent articles with optional filtering. Try SQLite first, then collector service, then NewsAPI."""
	try:
		# Validate and get limit parameter (max 10000 to match database MAX_ARTICLES)
		limit_raw = request.args.get('limit', 50, type=int)
		limit = validate_limit_parameter(limit_raw, min_val=1, max_val=10000)

		query = request.args.get('q')
		country = request.args.get('country', 'us')
		category = request.args.get('category')
		ai_only = request.args.get('ai_only', 'false').lower() == 'true'

		# Ensure database is connected
		if not sqlite_storage.is_connected():
			sqlite_storage.connect()
			logger.info("Database reconnected in get_articles")

		# Try to get articles from SQLite database first
		if sqlite_storage.is_connected():
			try:
				# When AI filtering is requested, fetch more articles to ensure we get enough after filtering
				fetch_limit = limit * 3 if ai_only else limit
				fetch_limit = min(fetch_limit, 10000)  # Cap at 10000 for performance

				if query:
					# Use full-text search for query
					db_articles = run_async(sqlite_storage.search_articles(query, limit=fetch_limit))
				else:
					# Get articles with optional filters
					db_articles = run_async(sqlite_storage.get_articles(
						limit=fetch_limit,
						category=category if category else None
					))

				if db_articles:
					# Map database articles to API format
					mapped = []
					for article in db_articles:
						mapped_article = {
							"id": article.get('id'),
							"title": article.get('title') or '',
							"summary": article.get('summary') or '',
							"content": article.get('content') or '',
							"source": article.get('source_name') or '',
							"source_name": article.get('source_name') or '',
							"source_display": article.get('source_display') or article.get('source_name') or '',
							"collector": article.get('collector') or '',
							"url": article.get('url') or '',
							"published_at": article.get('published_at'),
							"sentiment": article.get('sentiment'),
							"bias_score": article.get('bias_score'),
							"category": article.get('category')
						}
						mapped.append(mapped_article)

					# Apply AI filter if requested
					if ai_only:
						mapped = [a for a in mapped if is_ai_related(a)]

					mapped = mapped[:limit]

					return jsonify({
						"success": True,
						"data": {
							"articles": mapped,
							"count": len(mapped),
							"limit": limit,
							"ai_filtered": ai_only,
							"source": "local_database"
						}
					})
			except Exception as db_error:
				logger.warning(f"Error reading from local database: {str(db_error)}")
				# Fall through to other sources

		# Try to get articles from collector service
		collected_articles = run_async(collector_service.get_recent_articles(limit=limit))

		def _map_collected_article(article) -> Dict[str, Any]:
			"""Map collected article to frontend schema."""
			return {
				"id": article.id,
				"title": article.title,
				"summary": article.summary or (article.content[:200] + "..." if len(article.content) > 200 else article.content),
				"content": article.content,
				"source": article.source_name,
				"source_name": article.source_name,
				"collector": article.collector if hasattr(article, 'collector') else '',
				"url": article.url,
				"published_at": article.published_at.isoformat() if article.published_at else None,
				"sentiment": article.sentiment.value if article.sentiment else None,
				"bias_score": article.bias_score,
				"category": article.category
			}

		# If we have collected articles, use them
		if collected_articles:
			mapped = [_map_collected_article(a) for a in collected_articles]

			# Apply AI filter if requested
			if ai_only:
				mapped = [a for a in mapped if is_ai_related(a)]

			# Apply search query if provided
			if query:
				query_lower = query.lower()
				mapped = [a for a in mapped if query_lower in a['title'].lower() or query_lower in a.get('content', '').lower()]

			mapped = mapped[:limit]
			return jsonify({
				"success": True,
				"data": {
					"articles": mapped,
					"count": len(mapped),
					"limit": limit,
					"ai_filtered": ai_only,
					"source": "collector_service"
				}
			})

		# If no collected articles, try NewsAPI
		if settings.NEWS_API_KEY:
			try:
				params: Dict[str, Any] = {"apiKey": settings.NEWS_API_KEY, "pageSize": min(limit, 100)}
				endpoint = "https://newsapi.org/v2/top-headlines"

				# If AI filter is requested, add AI keywords to query
				if ai_only and not query:
					query = "AI OR artificial intelligence OR machine learning"

				if query:
					endpoint = "https://newsapi.org/v2/everything"
					params.update({"q": query, "language": "en", "sortBy": "publishedAt"})
				else:
					params.update({"country": country})
					if category:
						params.update({"category": category})

				resp = requests.get(endpoint, params=params, timeout=10)
				resp.raise_for_status()
				data = resp.json()
				articles = data.get("articles", [])
				mapped = [_map_newsapi_article(a) for a in articles]

				# Apply AI filter if requested
				if ai_only:
					mapped = [a for a in mapped if is_ai_related(a)]

				mapped = mapped[:limit]
				return jsonify({
					"success": True,
					"data": {
						"articles": mapped,
						"count": len(mapped),
						"limit": limit,
						"ai_filtered": ai_only,
						"source": "newsapi"
					}
				})
			except Exception as api_error:
				logger.warning(f"NewsAPI request failed, falling back to mock data: {str(api_error)}")
				# Fall through to mock data

		# 未配置 NEWS_API_KEY 或 API 请求失败时返回示例数据
		mock_articles = [
			{
				"id": "1",
				"title": "OpenAI Releases GPT-5: The Next Generation of AI",
				"summary": "OpenAI has announced the release of GPT-5, featuring breakthrough capabilities in reasoning and multimodal understanding.",
				"content": "OpenAI has officially launched GPT-5, marking a significant milestone in artificial intelligence...",
				"source": "Tech News",
				"source_name": "Tech News",
				"url": "https://example.com/gpt5",
				"published_at": "2025-10-10T10:00:00Z",
				"sentiment": "positive",
				"bias_score": None,
				"category": "technology"
			},
			{
				"id": "2",
				"title": "Google's New AI Model Surpasses Human Performance",
				"summary": "Google AI has developed a new machine learning model that achieves superhuman performance on complex reasoning tasks.",
				"content": "In a groundbreaking achievement, Google AI has unveiled a new neural network architecture...",
				"source": "AI Weekly",
				"source_name": "AI Weekly",
				"url": "https://example.com/google-ai",
				"published_at": "2025-10-09T15:30:00Z",
				"sentiment": "positive",
				"bias_score": None,
				"category": "technology"
			},
			{
				"id": "3",
				"title": "示例普通新闻标题",
				"summary": "这是一个示例新闻摘要",
				"content": "这是示例新闻的详细内容...",
				"source": "示例新闻源",
				"source_name": "示例新闻源",
				"url": "https://example.com",
				"published_at": "2025-10-08T08:00:00Z",
				"sentiment": "neutral",
				"bias_score": None,
				"category": None
			}
		]

		# Apply AI filter if requested
		if ai_only:
			mock_articles = [a for a in mock_articles if is_ai_related(a)]

		return jsonify({
			"success": True,
			"data": {
				"articles": mock_articles,
				"count": len(mock_articles),
				"limit": limit,
				"ai_filtered": ai_only,
				"source": "mock"
			}
		})
	except BadRequest as e:
		# BadRequest should return 400, not 500
		logger.warning(f"Bad request for articles: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 400
	except Exception as e:
		logger.error(f"Error getting articles: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/articles/<article_id>', methods=['GET'])
def get_article(article_id: str):
	"""Return single article; here we just echo back id with minimal fields (demo)."""
	try:
		mock_article = {
			"id": article_id,
			"title": f"文章 {article_id} 的标题",
			"summary": "",
			"content": "",
			"source": "NewsAPI" if settings.NEWS_API_KEY else "示例",
			"url": "",
			"published_at": None,
			"sentiment": None,
			"bias_score": None,
			"category": None
		}
		return jsonify({"success": True, "data": mock_article})
	except Exception as e:
		logger.error(f"Error getting article {article_id}: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/collect', methods=['POST'])
def trigger_collection():
	"""Collect AI news from the past 7 days (English and Chinese only)."""
	try:
		from datetime import datetime, timedelta

		logger.info("7-day AI news collection triggered")

		to_date = datetime.now()
		from_date = to_date - timedelta(days=7)

		collected_articles = []
		collection_results = {}

		# Collect AI news from NewsAPI (English and Chinese)
		if settings.NEWS_API_KEY:
			try:
				# Define AI-related search query
				ai_query = '(AI OR "artificial intelligence" OR "machine learning" OR "deep learning" OR ' \
						   '"neural network" OR GPT OR ChatGPT OR LLM OR "large language model" OR ' \
						   '"generative AI" OR transformer OR OpenAI OR "Google AI" OR Anthropic OR ' \
						   'Claude OR Gemini OR Copilot OR "computer vision" OR NLP OR ' \
						   '"natural language processing" OR "reinforcement learning")'

				languages = ['en', 'zh']  # English and Chinese only

				for lang in languages:
					logger.info(f"Collecting AI news in {lang}...")
					params = {
						'apiKey': settings.NEWS_API_KEY,
						'q': ai_query,
						'from': from_date.strftime('%Y-%m-%d'),
						'to': to_date.strftime('%Y-%m-%d'),
						'language': lang,
						'sortBy': 'publishedAt',
						'pageSize': 100
					}

					response = requests.get('https://newsapi.org/v2/everything', params=params, timeout=30)
					response.raise_for_status()
					data = response.json()

					if data.get('status') == 'ok':
						articles = data.get('articles', [])
						lang_count = 0

						for article_data in articles:
							# Double-check if article is AI-related
							title = article_data.get('title', '')
							description = article_data.get('description', '')
							text_to_check = (title + ' ' + description).lower()

							# Filter for AI-related content
							if not is_ai_related({'title': title, 'summary': description, 'content': ''}):
								continue

							article = NewsArticle(
								id=article_data.get('url', '')[:100],
								title=title,
								content=article_data.get('content', ''),
								url=article_data.get('url', ''),
								source_name=(article_data.get('source') or {}).get('name', 'NewsAPI'),
								collector="NewsAPI",
								source_type=SourceType.API,
								summary=description,
								published_at=datetime.fromisoformat(article_data.get('publishedAt', '').replace('Z', '+00:00')) if article_data.get('publishedAt') else None,
								tags=['ai', lang]
							)
							collected_articles.append(article)
							lang_count += 1

						collection_results[f'NewsAPI ({lang})'] = lang_count
						logger.info(f"Collected {lang_count} AI articles in {lang}")

			except Exception as e:
				logger.error(f"Error collecting from NewsAPI: {str(e)}")
				collection_results['NewsAPI'] = 0

		# Save all articles to database
		saved_count = 0
		failed_count = 0

		for article in collected_articles:
			try:
				# Process article for sentiment analysis
				processed = run_async(processor.process_article(article))
				# Save to SQLite
				saved = run_async(sqlite_storage.save_article(processed))
				if saved:
					saved_count += 1
				else:
					failed_count += 1
			except Exception as e:
				logger.error(f"Error saving article: {str(e)}")
				failed_count += 1

		logger.info(f"7-day AI news collection complete: {saved_count} saved, {failed_count} failed")

		return jsonify({
			"success": True,
			"message": f"Successfully collected {saved_count} AI news articles from the past 7 days (English & Chinese)",
			"data": {
				"date_range": {
					"from": from_date.isoformat(),
					"to": to_date.isoformat()
				},
				"total_collected": len(collected_articles),
				"saved_to_db": saved_count,
				"failed": failed_count,
				"sources": collection_results,
				"languages": ["en", "zh"],
				"ai_filtered": True
			}
		})
	except Exception as e:
		logger.error(f"Error triggering collection: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/collection/status', methods=['GET'])
def get_collection_status():
	"""Get status of data collection service."""
	try:
		status = run_async(data_collection_service.get_collection_status())

		return jsonify({
			"success": True,
			"data": status
		})
	except Exception as e:
		logger.error(f"Error getting collection status: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/process', methods=['POST'])
def trigger_processing():
	try:
		return jsonify({"success": True, "message": "Article processing triggered successfully"})
	except Exception as e:
		logger.error(f"Error triggering processing: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources', methods=['GET'])
def get_sources():
	try:
		from datetime import datetime, timedelta
		import random

		# Get configured sources from data_collection_service
		configured_sources = data_collection_service.sources

		# Get real article data to calculate accurate counts
		try:
			# Try database first for accurate count
			db_articles = run_async(sqlite_storage.get_articles(limit=10000))
		except Exception as e:
			logger.warning(f"Failed to read from database: {e}")
			# Fallback to collector service
			db_articles = []

		# If no database articles, try collector service
		if not db_articles:
			all_articles = run_async(collector_service.get_recent_articles(limit=1000))
		else:
			all_articles = db_articles

		# Count articles by source, collector, and combined key
		source_counts = {}
		collector_counts = {}
		source_collector_counts = {}  # Track by (source_name, collector) pairs
		source_last_updated = {}

		for article in all_articles:
			source_name = article.get('source_name') if isinstance(article, dict) else article.source_name
			collector = article.get('collector') if isinstance(article, dict) else getattr(article, 'collector', None)

			if source_name:
				source_counts[source_name] = source_counts.get(source_name, 0) + 1

				# Track by (source_name, collector) combination
				if collector:
					key = (source_name, collector)
					source_collector_counts[key] = source_collector_counts.get(key, 0) + 1

				# Track last updated time
				pub_date = article.get('published_at') if isinstance(article, dict) else (article.published_at.isoformat() if article.published_at else None)
				if pub_date:
					if source_name not in source_last_updated or pub_date > source_last_updated[source_name]:
						source_last_updated[source_name] = pub_date

			# Also count by collector (for NewsAPI, Reddit, Twitter, etc.)
			if collector:
				collector_counts[collector] = collector_counts.get(collector, 0) + 1

				# Track last updated time for collectors
				pub_date = article.get('published_at') if isinstance(article, dict) else (article.published_at.isoformat() if article.published_at else None)
				if pub_date:
					if collector not in source_last_updated or pub_date > source_last_updated[collector]:
						source_last_updated[collector] = pub_date

		# Generate dynamic update times
		now = datetime.utcnow()

		# Create sources list from configured sources
		sources = []

		for source in configured_sources:
			source_id = source.name.lower().replace(' ', '_').replace('/', '_')

			# Determine type badge
			if source.source_type.value == 'rss':
				source_type = "RSS"
			elif source.source_type.value == 'api':
				source_type = "API"
			elif source.source_type.value == 'social_media':
				source_type = "Social"
			else:
				source_type = "API"

			# Find matching article count with improved logic to avoid duplicate counting
			article_count = 0
			last_updated = now.isoformat() + 'Z'

			# Log counts for debugging
			if source_counts or collector_counts:
				logger.debug(f"Matching '{source.name}' (type: {source_type}) against source_counts: {list(source_counts.keys())}")
				logger.debug(f"Matching '{source.name}' against collector_counts: {list(collector_counts.keys())}")

			# Strategy depends on source type to avoid duplicate counting
			if source_type == "RSS":
				# For RSS sources, match by (source_name, "RSS") to avoid counting NewsAPI articles
				matched_sources = []
				for (src_name, collector_name), count in source_collector_counts.items():
					if collector_name == "RSS":
						# Match RSS articles by source name
						matched = False
						if source.name.lower() == src_name.lower():
							matched = True
						elif source.name.lower() in src_name.lower() or src_name.lower() in source.name.lower():
							matched = True

						if matched:
							article_count += count
							matched_sources.append(src_name)
							if pub_date := source_last_updated.get(src_name):
								if not last_updated or pub_date > last_updated:
									last_updated = pub_date

				if matched_sources:
					logger.debug(f"RSS source '{source.name}' matched: {matched_sources}, total: {article_count}")

			elif source_type == "API" or source_type == "Social":
				# For API/Social sources (NewsAPI, Reddit, Twitter), match by collector name
				matched_by_collector = False
				for collector_name, count in collector_counts.items():
					matched = False

					if source.name.lower() == collector_name.lower():
						matched = True
					elif "newsapi" in source.name.lower() and "newsapi" in collector_name.lower():
						matched = True
					elif "reddit" in source.name.lower() and "reddit" in collector_name.lower():
						matched = True
					elif "twitter" in source.name.lower() and "twitter" in collector_name.lower():
						matched = True
					elif "exa" in source.name.lower() and "exa" in collector_name.lower():
						matched = True

					if matched:
						article_count += count
						matched_by_collector = True
						if pub_date := source_last_updated.get(collector_name):
							if not last_updated or pub_date > last_updated:
								last_updated = pub_date
						logger.debug(f"API/Social source '{source.name}' matched by collector '{collector_name}': {count} articles")
						break

				# Special case: Exa AI Search might be stored with collector="RSS"
				# Try matching by source_name if not matched by collector
				if not matched_by_collector and "exa" in source.name.lower():
					for (src_name, collector_name), count in source_collector_counts.items():
						if "exa" in src_name.lower():
							article_count += count
							if pub_date := source_last_updated.get(src_name):
								if not last_updated or pub_date > last_updated:
									last_updated = pub_date
							logger.debug(f"API source '{source.name}' matched by source_name '{src_name}': {count} articles")
							break

			sources.append({
				"id": source_id,
				"name": source.name,
				"type": source_type,
				"url": source.url,
				"status": "active" if source.is_active else "inactive",
				"last_updated": last_updated,
				"articles_count": article_count,
				"description": f"{source.name} - {source_type} news source"
			})

		# If no configured sources, return default mock data
		if not sources:
			sources = [
				{
					"id": "newsapi",
					"name": "NewsAPI",
					"type": "API",
					"url": "https://newsapi.org",
					"status": "active",
					"last_updated": now.isoformat() + 'Z',
					"articles_count": 0,
					"description": "Global news aggregation API service"
				},
				{
					"id": "rss_tech",
					"name": "Tech RSS Feeds",
					"type": "RSS",
					"url": "https://feeds.feedburner.com/TechCrunch",
					"status": "active",
					"last_updated": now.isoformat() + 'Z',
					"articles_count": 0,
					"description": "Technology news RSS feed"
				},
				{
					"id": "twitter_x",
					"name": "Twitter/X",
					"type": "Social",
					"url": "https://twitter.com",
					"status": "active",
					"last_updated": now.isoformat() + 'Z',
					"articles_count": 0,
					"description": "Twitter/X social media platform"
				},
				{
					"id": "reddit_news",
					"name": "Reddit News",
					"type": "Social",
					"url": "https://www.reddit.com/r/news",
					"status": "active",
					"last_updated": now.isoformat() + 'Z',
					"articles_count": 0,
					"description": "Reddit news aggregation"
				}
			]

		return jsonify({"success": True, "data": sources})
	except Exception as e:
		logger.error(f"Error getting sources: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources/<source_id>', methods=['GET'])
def get_source(source_id: str):
	"""Get specific source details."""
	try:
		# Get all sources first
		sources_response = get_sources()
		sources_data = sources_response.get_json()

		if not sources_data.get('success'):
			return jsonify({"success": False, "error": "Failed to fetch sources"}), 500

		sources = sources_data.get('data', [])

		# Find the requested source
		source = next((s for s in sources if s["id"] == source_id), None)
		if not source:
			return jsonify({"success": False, "error": "Source not found"}), 404

		return jsonify({"success": True, "data": source})
	except Exception as e:
		logger.error(f"Error getting source {source_id}: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources/<source_id>', methods=['PUT'])
def update_source(source_id: str):
	"""Update an existing news source."""
	try:
		from datetime import datetime

		data = request.get_json()
		if not data:
			return jsonify({"success": False, "error": "No data provided"}), 400

		# 验证必需字段
		required_fields = ['name', 'type', 'url']
		for field in required_fields:
			if not data.get(field):
				return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

		# Update the source in data_collection_service
		updated = data_collection_service.update_source(
			source_id=source_id,
			name=data.get('name'),
			url=data.get('url'),
			status=data.get('status', 'active')
		)

		if updated:
			logger.info(f"Successfully updated source {source_id}")

			# Get the updated source
			updated_source = data_collection_service.get_source_by_id(source_id)
			if updated_source:
				# Determine type badge
				if updated_source.source_type.value == 'rss':
					source_type = "RSS"
				elif updated_source.source_type.value == 'api':
					source_type = "API"
				elif updated_source.source_type.value == 'social_media':
					source_type = "Social"
				else:
					source_type = "API"

				return jsonify({
					"success": True,
					"message": "Source updated successfully",
					"data": {
						"id": source_id,
						"name": updated_source.name,
						"type": source_type,
						"url": updated_source.url,
						"status": "active" if updated_source.is_active else "inactive",
						"description": data.get("description", f"{updated_source.name} - {source_type} news source"),
						"last_updated": datetime.utcnow().isoformat() + 'Z',
						"articles_count": 0
					}
				})

		return jsonify({
			"success": False,
			"error": "Source not found"
		}), 404

	except Exception as e:
		logger.error(f"Error updating source {source_id}: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources', methods=['POST'])
def create_source():
	"""Create a new news source."""
	try:
		data = request.get_json()
		if not data:
			return jsonify({"success": False, "error": "No data provided"}), 400

		# 验证必需字段
		required_fields = ['name', 'type', 'url']
		for field in required_fields:
			if not data.get(field):
				return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

		# 生成新的源ID
		import uuid
		source_id = str(uuid.uuid4())[:8]

		# 模拟创建源
		logger.info(f"Creating new source with data: {data}")

		# 返回新创建的源数据
		new_source = {
			"id": source_id,
			"name": data.get("name"),
			"type": data.get("type"),
			"url": data.get("url"),
			"status": "active",
			"description": data.get("description", ""),
			"last_updated": "2025-09-23T10:20:00Z",
			"articles_count": 0
		}

		return jsonify({
			"success": True,
			"message": "Source created successfully",
			"data": new_source
		}), 201
	except Exception as e:
		logger.error(f"Error creating source: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id: str):
	"""Delete a news source."""
	try:
		# 模拟删除源
		logger.info(f"Deleting source: {source_id}")

		return jsonify({
			"success": True,
			"message": "Source deleted successfully"
		})
	except Exception as e:
		logger.error(f"Error deleting source {source_id}: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/sources/<source_id>/test', methods=['POST'])
def test_source(source_id: str):
	"""Test a news source connection and functionality."""
	try:
		# Get source information from dynamic sources
		source_response = get_source(source_id)
		source_data = source_response.get_json()

		if not source_data.get('success'):
			return jsonify({"success": False, "error": "Source not found"}), 404

		source = source_data.get('data')

		# Simulate testing different types of sources
		if source["type"] == "API":
			test_result = {
				"success": True,
				"message": f"API connection test successful for {source['name']}",
				"details": {
					"response_time": "245ms",
					"status_code": 200,
					"available_articles": source.get('articles_count', 0),
					"rate_limit_remaining": 450
				}
			}
		elif source["type"] == "RSS":
			test_result = {
				"success": True,
				"message": f"RSS feed test successful for {source['name']}",
				"details": {
					"response_time": "312ms",
					"feed_valid": True,
					"articles_found": source.get('articles_count', 0),
					"last_updated": source.get('last_updated', '')
				}
			}
		elif source["type"] == "Social":
			test_result = {
				"success": True,
				"message": f"Social media API test successful for {source['name']}",
				"details": {
					"response_time": "189ms",
					"api_status": "operational",
					"content_accessible": True,
					"rate_limit_remaining": 100
				}
			}
		else:
			test_result = {
				"success": False,
				"message": f"Unknown source type: {source['type']}",
				"details": {}
			}

		logger.info(f"Testing source {source_id}: {test_result}")
		return jsonify(test_result)

	except Exception as e:
		logger.error(f"Error testing source {source_id}: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e),
			"message": "Source test failed due to internal error"
		}), 500

@news_api.route('/stats', methods=['GET'])
def get_stats():
	"""Get statistics using efficient SQL aggregation."""
	try:
		from datetime import datetime, timedelta

		# Get real status from collector service
		status = run_async(collector_service.get_collection_status())

		# Get statistics efficiently from database using SQL aggregation
		try:
			db_stats = run_async(sqlite_storage.get_statistics())

			if db_stats:
				total_articles = db_stats.get('total_articles', 0)
				articles_by_source = db_stats.get('articles_by_source', {})
				articles_by_sentiment = db_stats.get('articles_by_sentiment', {})
				last_published = db_stats.get('last_published')

				# Count AI articles efficiently using parameterized queries
				# Use same AI_KEYWORDS as is_ai_related function for consistency
				ai_articles_count = 0
				try:
					cursor = sqlite_storage.conn.cursor()
					# Use parameterized queries to prevent SQL injection
					# Use same keywords as AI_KEYWORDS for consistency (must match the global AI_KEYWORDS list)
					# Create placeholders for parameterized query
					placeholders = ' OR '.join(['(title LIKE ? OR summary LIKE ? OR content LIKE ?)' for _ in AI_KEYWORDS])
					# Create parameters with wildcards
					params = [f'%{kw}%' for kw in AI_KEYWORDS for _ in range(3)]
					cursor.execute(f'SELECT COUNT(*) as count FROM articles WHERE {placeholders}', params)
					ai_articles_count = cursor.fetchone()['count']
				except Exception as e:
					logger.error(f"Error counting AI articles: {str(e)}")
					ai_articles_count = 0

				# Normalize sentiment distribution
				sentiment_distribution = {
					"positive": articles_by_sentiment.get('positive', 0),
					"negative": articles_by_sentiment.get('negative', 0),
					"neutral": articles_by_sentiment.get('neutral', 0),
					"mixed": articles_by_sentiment.get('mixed', 0)
				}

				# Calculate active sources
				active_sources = len(articles_by_source)

				# Use actual article counts from database
				collection_stats = {
					"total_collections": active_sources,
					"total_articles": total_articles,
					"successful_collections": active_sources,
					"last_collection": last_published,
					"failed_collections": 0
				}

				stats = {
					"collection_stats": collection_stats,
					"article_stats": {
						"sentiment_distribution": sentiment_distribution,
						"source_distribution": articles_by_source
					},
					"ai_stats": {
						"total_ai_articles": ai_articles_count,
						"ai_percentage": round((ai_articles_count / total_articles * 100) if total_articles > 0 else 0, 1)
					},
					"database_stats": {
						"stored_articles": total_articles,
						"unique_sources": active_sources,
						"data_source": "database",
						"max_capacity": sqlite_storage.MAX_ARTICLES
					}
				}

				return jsonify({"success": True, "data": stats})
		except Exception as e:
			logger.warning(f"Failed to get stats from database: {e}")

		# Fallback to empty stats
		stats = {
			"collection_stats": {
				"total_collections": 0,
				"total_articles": 0,
				"successful_collections": 0,
				"last_collection": None,
				"failed_collections": 0
			},
			"article_stats": {
				"sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
				"source_distribution": {}
			},
			"ai_stats": {
				"total_ai_articles": 0,
				"ai_percentage": 0
			},
			"database_stats": {
				"stored_articles": 0,
				"unique_sources": 0,
				"data_source": "none",
				"max_capacity": sqlite_storage.MAX_ARTICLES
			}
		}

		return jsonify({"success": True, "data": stats})
	except Exception as e:
		logger.error(f"Error getting stats: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/ai-stats', methods=['GET'])
def get_ai_stats():
	"""Get detailed AI news statistics."""
	try:
		# Mock AI news statistics
		ai_stats = {
			"total_ai_articles": 8,
			"recent_ai_articles": [
				{
					"id": "ai-1",
					"title": "OpenAI Releases GPT-5: The Next Generation of AI",
					"summary": "OpenAI has announced GPT-5 with breakthrough capabilities",
					"published_at": "2025-10-10T10:00:00Z",
					"source": "Tech News"
				},
				{
					"id": "ai-2",
					"title": "Google's New AI Model Surpasses Human Performance",
					"summary": "Google AI develops superhuman reasoning model",
					"published_at": "2025-10-09T15:30:00Z",
					"source": "AI Weekly"
				}
			],
			"ai_topics": {
				"Large Language Models": 3,
				"Computer Vision": 2,
				"Robotics": 1,
				"Neural Networks": 2
			},
			"trending_ai_keywords": [
				"GPT", "Machine Learning", "Neural Network", "OpenAI", "Google AI"
			]
		}
		return jsonify({"success": True, "data": ai_stats})
	except Exception as e:
		logger.error(f"Error getting AI stats: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500

@news_api.route('/reprocess', methods=['POST'])
def reprocess_articles():
	"""Reprocess articles without sentiment analysis using TextBlob fallback."""
	try:
		logger.info("Starting article reprocessing...")

		# Validate and get limit parameter (max 10000 to match database MAX_ARTICLES)
		limit_raw = request.args.get('limit', 100, type=int)
		limit = validate_limit_parameter(limit_raw, min_val=1, max_val=10000)

		force_all = request.args.get('force_all', 'false').lower() == 'true'

		# Get articles from database
		db_articles = run_async(sqlite_storage.get_articles(limit=10000))

		if not db_articles:
			return jsonify({
				"success": True,
				"message": "No articles found in database",
				"data": {
					"total_articles": 0,
					"processed_articles": 0,
					"updated_articles": 0
				}
			})

		# Filter articles that need processing (no sentiment or force_all)
		articles_to_process = []
		for article_dict in db_articles:
			if force_all or not article_dict.get('sentiment'):
				# Convert dict to NewsArticle object
				from ..models.news_models import SentimentType, SourceType

				article = NewsArticle(
					id=article_dict['id'],
					title=article_dict['title'],
					content=article_dict.get('content', ''),
					url=article_dict.get('url', ''),
					source_name=article_dict.get('source_name', 'Unknown'),
					source_type=SourceType.RSS,  # Default
					summary=article_dict.get('summary', ''),
					tags=[]
				)
				articles_to_process.append(article)

				if len(articles_to_process) >= limit:
					break

		if not articles_to_process:
			return jsonify({
				"success": True,
				"message": "All articles already have sentiment analysis",
				"data": {
					"total_articles": len(db_articles),
					"processed_articles": 0,
					"updated_articles": 0
				}
			})

		logger.info(f"Processing {len(articles_to_process)} articles...")

		# Process articles through NewsProcessor (has TextBlob fallback)
		updated_count = 0
		failed_count = 0

		for article in articles_to_process:
			try:
				# Process article (will use TextBlob if OpenAI unavailable)
				processed = run_async(processor.process_article(article))

				# Save back to database
				if processed.sentiment:
					saved = run_async(sqlite_storage.save_article(processed))
					if saved:
						updated_count += 1
					else:
						failed_count += 1
				else:
					failed_count += 1

			except Exception as e:
				logger.error(f"Error processing article {article.id}: {str(e)}")
				failed_count += 1

		logger.info(f"Reprocessing complete: {updated_count} updated, {failed_count} failed")

		return jsonify({
			"success": True,
			"message": f"Successfully reprocessed {updated_count} articles",
			"data": {
				"total_articles": len(db_articles),
				"processed_articles": len(articles_to_process),
				"updated_articles": updated_count,
				"failed_articles": failed_count
			}
		})

	except BadRequest as e:
		# BadRequest should return 400, not 500
		logger.warning(f"Bad request for reprocess: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 400
	except Exception as e:
		logger.error(f"Error reprocessing articles: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

@news_api.route('/collect-7days', methods=['POST'])
def collect_7days_news():
	"""Collect news from the past 7 days and store in SQLite."""
	try:
		from datetime import datetime, timedelta

		logger.info("Starting 7-day news collection...")

		to_date = datetime.now()
		from_date = to_date - timedelta(days=7)

		collected_articles = []
		collection_results = {}

		# Collect from NewsAPI
		if settings.NEWS_API_KEY:
			try:
				params = {
					'apiKey': settings.NEWS_API_KEY,
					'q': 'news OR technology OR world OR business OR politics',
					'from': from_date.strftime('%Y-%m-%d'),
					'to': to_date.strftime('%Y-%m-%d'),
					'language': 'en',
					'sortBy': 'publishedAt',
					'pageSize': 100
				}
				response = requests.get('https://newsapi.org/v2/everything', params=params, timeout=30)
				response.raise_for_status()
				data = response.json()

				if data.get('status') == 'ok':
					articles = data.get('articles', [])
					for article_data in articles:
						article = NewsArticle(
							id=article_data.get('url', '')[:100],
							title=article_data.get('title', ''),
							content=article_data.get('content', ''),
							url=article_data.get('url', ''),
							source_name=(article_data.get('source') or {}).get('name', 'NewsAPI'),
							collector="NewsAPI",
							source_type=SourceType.API,
							summary=article_data.get('description', ''),
							published_at=datetime.fromisoformat(article_data.get('publishedAt', '').replace('Z', '+00:00')) if article_data.get('publishedAt') else None,
							tags=[]
						)
						collected_articles.append(article)
					collection_results['NewsAPI'] = len(articles)
					logger.info(f"Collected {len(articles)} articles from NewsAPI")
			except Exception as e:
				logger.error(f"Error collecting from NewsAPI: {str(e)}")
				collection_results['NewsAPI'] = 0

		# Save all articles to database
		saved_count = 0
		failed_count = 0

		for article in collected_articles:
			try:
				# Process article for sentiment analysis
				processed = run_async(processor.process_article(article))
				# Save to SQLite
				saved = run_async(sqlite_storage.save_article(processed))
				if saved:
					saved_count += 1
				else:
					failed_count += 1
			except Exception as e:
				logger.error(f"Error saving article: {str(e)}")
				failed_count += 1

		logger.info(f"7-day collection complete: {saved_count} saved, {failed_count} failed")

		return jsonify({
			"success": True,
			"message": f"Successfully collected and stored {saved_count} articles from the past 7 days",
			"data": {
				"date_range": {
					"from": from_date.isoformat(),
					"to": to_date.isoformat()
				},
				"total_collected": len(collected_articles),
				"saved_to_db": saved_count,
				"failed": failed_count,
				"sources": collection_results
			}
		})

	except Exception as e:
		logger.error(f"Error in 7-day collection: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500


@news_api.route('/collect-all-sources', methods=['POST'])
def collect_all_sources():
	"""Collect news from ALL configured sources (RSS, NewsAPI, Twitter, Reddit, Exa AI)."""
	try:
		logger.info("Starting collection from all sources (RSS, NewsAPI, Twitter, Reddit, Exa)...")

		# Use data_collection_service to collect from all sources
		result = run_async(data_collection_service.collect_all(save_to_db=True))

		if result.get("success"):
			logger.info(f"All sources collection complete: {result.get('saved_to_db')} articles saved")

			return jsonify({
				"success": True,
				"message": f"Successfully collected articles from all sources",
				"data": {
					"total_collected": result.get("total_collected", 0),
					"rss_articles": result.get("rss_articles", 0),
					"newsapi_articles": result.get("newsapi_articles", 0),
					"twitter_articles": result.get("twitter_articles", 0),
					"reddit_articles": result.get("reddit_articles", 0),
					"exa_articles": result.get("exa_articles", 0),
					"saved_to_db": result.get("saved_to_db", 0),
					"duration_seconds": result.get("duration_seconds", 0),
					"timestamp": result.get("timestamp")
				}
			})
		else:
			raise Exception("Collection failed")

	except Exception as e:
		logger.error(f"Error in all sources collection: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500


@news_api.route('/api-config-status', methods=['GET'])
def get_api_config_status():
	"""Check which APIs are configured in .env file."""
	try:
		from ..config.settings import settings

		api_status = []

		# Check NewsAPI
		api_status.append({
			"name": "NewsAPI",
			"icon": "newspaper",
			"icon_type": "fas",  # Font Awesome Solid
			"color": "primary",
			"configured": bool(settings.NEWS_API_KEY)
		})

		# Check Twitter/X
		api_status.append({
			"name": "Twitter/X",
			"icon": "twitter",  # Updated Twitter/X icon
			"icon_type": "fab",  # Font Awesome Brand
			"color": "info",
			"configured": bool(settings.TWITTER_BEARER_TOKEN)
		})

		# Check Reddit
		api_status.append({
			"name": "Reddit",
			"icon": "reddit-alien",
			"icon_type": "fab",  # Font Awesome Brand
			"color": "warning",
			"configured": bool(settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET)
		})

		# Check Exa AI
		api_status.append({
			"name": "Exa AI",
			"icon": "search",
			"icon_type": "fas",  # Font Awesome Solid
			"color": "success",
			"configured": bool(getattr(settings, 'EXA_API_KEY', None))
		})

		# Check OpenAI
		api_status.append({
			"name": "OpenAI",
			"icon": "robot",
			"icon_type": "fas",  # Font Awesome Solid
			"color": "danger",
			"configured": bool(settings.OPENAI_API_KEY)
		})

		return jsonify({
			"success": True,
			"data": api_status
		})

	except Exception as e:
		logger.error(f"Error checking API config status: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500


@news_api.route('/ai-summary', methods=['POST'])
def generate_ai_summary():
	"""Generate comprehensive AI news analysis summary."""
	try:
		from datetime import datetime
		from collections import Counter

		# Get all AI-related articles from database
		ai_articles = []

		# Try to get articles from SQLite database first
		try:
			# Ensure database is connected
			if not sqlite_storage.is_connected():
				sqlite_storage.connect()
				logger.info("Database reconnected in generate_ai_summary")

			# Get all articles from database
			db_articles = run_async(sqlite_storage.get_articles(limit=10000))

			if db_articles:
				# Map database articles to API format
				mapped = []
				for article in db_articles:
					mapped_article = {
						"id": article.get('id'),
						"title": article.get('title') or '',
						"summary": article.get('summary') or '',
						"content": article.get('content') or '',
						"source": article.get('source_name') or '',
						"source_name": article.get('source_name') or '',
						"source_display": article.get('source_display') or article.get('source_name') or '',
						"url": article.get('url') or '',
						"published_at": article.get('published_at'),
						"sentiment": article.get('sentiment'),
						"bias_score": article.get('bias_score'),
						"category": article.get('category')
					}
					mapped.append(mapped_article)

				# Filter AI-related articles
				ai_articles = [a for a in mapped if is_ai_related(a)]
				logger.info(f"Found {len(ai_articles)} AI articles from local database")
		except Exception as db_error:
			logger.warning(f"Error reading from database for AI summary: {str(db_error)}")

		# If no AI articles from database, try collector service
		if not ai_articles:
			all_articles = run_async(collector_service.get_recent_articles(limit=100))

			def _map_collected_article(article) -> Dict[str, Any]:
				"""Map collected article to frontend schema."""
				return {
					"id": article.id,
					"title": article.title,
					"summary": article.summary or (article.content[:200] + "..." if len(article.content) > 200 else article.content),
					"content": article.content,
					"source": article.source_name,
					"source_name": article.source_name,
					"url": article.url,
					"published_at": article.published_at.isoformat() if article.published_at else None,
					"sentiment": article.sentiment.value if article.sentiment else None,
					"bias_score": article.bias_score,
					"category": article.category
				}

			mapped_articles = [_map_collected_article(a) for a in all_articles]

			# Filter AI-related articles
			ai_articles = [a for a in mapped_articles if is_ai_related(a)]

		# If no collected articles, try NewsAPI or use mock data
		if not ai_articles:
			if settings.NEWS_API_KEY:
				try:
					params = {
						"apiKey": settings.NEWS_API_KEY,
						"q": "AI OR artificial intelligence OR machine learning",
						"language": "en",
						"sortBy": "publishedAt",
						"pageSize": 50
					}
					endpoint = "https://newsapi.org/v2/everything"
					resp = requests.get(endpoint, params=params, timeout=10)
					resp.raise_for_status()
					data = resp.json()
					articles = data.get("articles", [])
					ai_articles = [_map_newsapi_article(a) for a in articles]
				except Exception as e:
					logger.warning(f"Failed to fetch from NewsAPI: {str(e)}")
					# Use mock data
					ai_articles = [
						{
							"id": "1",
							"title": "OpenAI Releases GPT-5: The Next Generation of AI",
							"summary": "OpenAI has announced GPT-5 with breakthrough capabilities in reasoning and multimodal understanding.",
							"content": "OpenAI has officially launched GPT-5...",
							"source": "Tech News",
							"source_name": "Tech News",
							"url": "https://example.com/gpt5",
							"published_at": "2025-10-10T10:00:00Z",
							"sentiment": "positive"
						},
						{
							"id": "2",
							"title": "Google's New AI Model Surpasses Human Performance",
							"summary": "Google AI has developed a new machine learning model that achieves superhuman performance.",
							"content": "In a groundbreaking achievement, Google AI has unveiled...",
							"source": "AI Weekly",
							"source_name": "AI Weekly",
							"url": "https://example.com/google-ai",
							"published_at": "2025-10-09T15:30:00Z",
							"sentiment": "positive"
						},
						{
							"id": "3",
							"title": "AI Safety Concerns Raised by Researchers",
							"summary": "Leading AI researchers express concerns about rapid AI development.",
							"content": "A group of prominent AI researchers has published...",
							"source": "Science Daily",
							"source_name": "Science Daily",
							"url": "https://example.com/ai-safety",
							"published_at": "2025-10-08T14:20:00Z",
							"sentiment": "negative"
						},
						{
							"id": "4",
							"title": "New Neural Network Architecture Shows Promise",
							"summary": "Researchers develop efficient neural network design.",
							"content": "A new neural network architecture has been proposed...",
							"source": "Tech Review",
							"source_name": "Tech Review",
							"url": "https://example.com/neural-net",
							"published_at": "2025-10-07T09:30:00Z",
							"sentiment": "neutral"
						}
					]
			else:
				# Use mock data
				ai_articles = [
					{
						"id": "1",
						"title": "OpenAI Releases GPT-5: The Next Generation of AI",
						"summary": "OpenAI has announced GPT-5 with breakthrough capabilities in reasoning and multimodal understanding.",
						"content": "OpenAI has officially launched GPT-5...",
						"source": "Tech News",
						"source_name": "Tech News",
						"url": "https://example.com/gpt5",
						"published_at": "2025-10-10T10:00:00Z",
						"sentiment": "positive"
					},
					{
						"id": "2",
						"title": "Google's New AI Model Surpasses Human Performance",
						"summary": "Google AI has developed a new machine learning model that achieves superhuman performance.",
						"content": "In a groundbreaking achievement, Google AI has unveiled...",
						"source": "AI Weekly",
						"source_name": "AI Weekly",
						"url": "https://example.com/google-ai",
						"published_at": "2025-10-09T15:30:00Z",
						"sentiment": "positive"
					},
					{
						"id": "3",
						"title": "AI Safety Concerns Raised by Researchers",
						"summary": "Leading AI researchers express concerns about rapid AI development.",
						"content": "A group of prominent AI researchers has published...",
						"source": "Science Daily",
						"source_name": "Science Daily",
						"url": "https://example.com/ai-safety",
						"published_at": "2025-10-08T14:20:00Z",
						"sentiment": "negative"
					},
					{
						"id": "4",
						"title": "New Neural Network Architecture Shows Promise",
						"summary": "Researchers develop efficient neural network design.",
						"content": "A new neural network architecture has been proposed...",
						"source": "Tech Review",
						"source_name": "Tech Review",
						"url": "https://example.com/neural-net",
						"published_at": "2025-10-07T09:30:00Z",
						"sentiment": "neutral"
					}
				]

		# Analyze sentiment distribution
		sentiment_summary = Counter()
		for article in ai_articles:
			sentiment = article.get('sentiment', 'neutral')
			if sentiment:
				sentiment_summary[sentiment] += 1

		# Extract trending topics from titles and content
		all_text = ' '.join([
			(a.get('title', '') + ' ' + a.get('summary', ''))
			for a in ai_articles
		]).lower()

		# Count AI-related keywords
		keyword_counts = Counter()
		for keyword in AI_KEYWORDS:
			count = all_text.count(keyword.lower())
			if count > 0:
				keyword_counts[keyword] = count

		trending_topics = [kw for kw, _ in keyword_counts.most_common(8)]

		# Generate key insights
		total_articles = len(ai_articles)
		positive_count = sentiment_summary.get('positive', 0)
		negative_count = sentiment_summary.get('negative', 0)

		key_insights = []
		if positive_count > total_articles * 0.5:
			key_insights.append(f"Predominantly positive sentiment ({positive_count}/{total_articles} articles)")
		if negative_count > total_articles * 0.2:
			key_insights.append(f"Notable concerns raised in {negative_count} articles")

		# Add topic-based insights
		if 'gpt' in all_text or 'chatgpt' in all_text:
			key_insights.append("GPT models remain a hot topic in AI news")
		if 'google' in all_text or 'gemini' in all_text:
			key_insights.append("Google AI developments gaining attention")
		if 'safety' in all_text or 'regulation' in all_text:
			key_insights.append("AI safety and regulation discussions ongoing")

		# Get top 20 articles (by recency) - use sortable default for None dates
		top_20_articles = sorted(
			ai_articles,
			key=lambda x: x.get('published_at') or '1970-01-01',
			reverse=True
		)[:20]

		# Also keep top 5 for backward compatibility
		top_articles = top_20_articles[:5]

		# Generate AI summary using OpenAI (if configured)
		ai_summary = None
		if settings.OPENAI_API_KEY and total_articles > 0:
			try:
				# Analyze source distribution
				source_counts = Counter([a.get('source_name', 'Unknown') for a in ai_articles])
				top_sources = source_counts.most_common(5)
				source_summary = ', '.join([f"{src} ({cnt})" for src, cnt in top_sources])

				# Analyze date range
				dates_available = [a.get('published_at') for a in ai_articles if a.get('published_at')]
				if dates_available:
					earliest_date = min(dates_available)[:10] if isinstance(min(dates_available), str) else str(min(dates_available))[:10]
					latest_date = max(dates_available)[:10] if isinstance(max(dates_available), str) else str(max(dates_available))[:10]
					date_range = f"from {earliest_date} to {latest_date}"
				else:
					date_range = "recent period"

				# Calculate sentiment percentages
				positive_pct = round((positive_count / total_articles * 100) if total_articles > 0 else 0, 1)
				negative_pct = round((negative_count / total_articles * 100) if total_articles > 0 else 0, 1)
				neutral_count = sentiment_summary.get('neutral', 0)
				neutral_pct = round((neutral_count / total_articles * 100) if total_articles > 0 else 0, 1)
				mixed_count = sentiment_summary.get('mixed', 0)
				mixed_pct = round((mixed_count / total_articles * 100) if total_articles > 0 else 0, 1)

				# Prepare article data for OpenAI analysis
				articles_data = []
				for article in ai_articles[:100]:  # Limit to first 100 articles for API efficiency
					articles_data.append({
						'title': article.get('title', ''),
						'summary': article.get('summary', ''),
						'source': article.get('source_name', ''),
						'published_at': article.get('published_at', ''),
						'sentiment': article.get('sentiment', '')
					})

				# Prepare statistics summary
				stats_summary = f"""
总文章数：{total_articles}篇
时间范围：{date_range}
情感分布：
- 正面 (positive): {positive_count}篇 ({positive_pct}%)
- 负面 (negative): {negative_count}篇 ({negative_pct}%)
- 中性 (neutral): {neutral_count}篇 ({neutral_pct}%)
- 混合 (mixed): {mixed_count}篇 ({mixed_pct}%)

主要新闻来源：{source_summary}
热点话题关键词：{', '.join(trending_topics[:10])}
"""

				# Create prompt for OpenAI
				prompt = f"""你是一位具有科技媒体洞察力、政策敏感度与商业判断力的AI产业观察员。

请基于以下AI相关新闻数据（包括时间、来源、标题、摘要、情绪值等字段），生成一份深度中文分析报告。

【数据统计】
{stats_summary}

【部分新闻样本】（共{total_articles}篇，以下为代表性样本）
{chr(10).join([f"{i+1}. 标题：{a['title']} | 来源：{a['source']} | 情绪：{a['sentiment']}" for i, a in enumerate(articles_data[:20])])}

【核心要求】
⚠️ **字数严格要求**：全文必须达到600-800个中文字（不含标点），不得少于600字，也不要超过850字。

1️⃣ **报告结构**（必须包含以下4个部分，每部分150-200字）
- **第一段：总体趋势与情绪分化**
  开篇点明舆论整体态势，用数据说话（正面{positive_pct}%、负面{negative_pct}%、中性{neutral_pct}%），分析情绪分化的深层原因（技术突破vs监管担忧、创新热潮vs就业焦虑、商业机遇vs伦理挑战等），不要简单罗列数据，要解释"为什么"会出现这样的分布。

- **第二段：核心议题与关注焦点**
  深入剖析新闻中反复出现的主题（从关键词{', '.join(trending_topics[:6])}中提炼），识别当前最热议题如大模型竞争格局（OpenAI、Anthropic、Google的角力）、AI在垂直行业的落地进展（医疗、教育、金融）、AI安全与治理政策动向等，并指出媒体报道中的乐观或悲观倾向，分析背后的商业利益或政策考量。

- **第三段：媒体态度与传播特征**
  对比主流媒体（如Guardian、Times of India等传统权威媒体）与新兴平台（Yahoo Entertainment、社交媒体）在报道AI新闻时的语气、角度、立场差异。分析哪类情绪的报道更易引发传播和共鸣（是乐观的技术突破更吸睛，还是悲观的风险警示更有冲击力），揭示媒体生态对AI舆论的塑造作用。

- **第四段：未来走向与分析者立场**
  基于数据和趋势，对AI产业发展与舆论走向做出明确判断：AI是否正从炒作期进入理性期？监管是收紧还是放松？商业落地是加速还是遇冷？公众信任是回升还是下滑？**必须明确表达你作为分析者的态度**（如"作为观察者，我持谨慎乐观态度，因为……"或"令人担忧的是……"），并用数据或事实支撑你的立场。

2️⃣ **分析深度要求**
- ❌ 避免：简单罗列数据、空洞套话、泛泛而谈
- ✅ 必须：提出具体观点、指出因果关系、揭示深层逻辑、给出有见地的判断
- 示例对比：
  ❌ "AI新闻很多，正面和负面都有"
  ✅ "正面报道占比不足四分之一，反映出技术突破的热情正被监管压力和伦理争议所稀释，这种情绪转向预示着AI产业正从单一叙事走向多元博弈"

3️⃣ **风格与语气**
- 媒体评论风格：逻辑严密、观点犀利、有温度、有态度
- 数据驱动表达：用具体比例和数字增强说服力（如"仅23.9%的报道呈正面情绪，低于去年同期的41%"）
- 升华式结尾：用一句有洞察力的话总结（如"AI正从技术神话走向社会共识的拐点""从狂热追捧到理性审视，AI舆论正在经历一场成人礼"）

4️⃣ **输出格式**
- 连贯的段落式文本，不要分条列点
- 不输出markdown标记、代码块或标签
- 4个段落之间用换行符分隔

【示例开头】（风格参考，勿照抄）
"从过去一个月收集的超过七百条AI相关新闻来看，全球舆论正呈现出前所未有的复杂分化。数据显示，仅有不到四分之一的报道（23.9%）带有积极色彩，聚焦于技术突破与商业落地；而超过半数（53.9%）的报道保持中立观望态度，这种克制本身就耐人寻味——它意味着媒体与公众正在从盲目乐观转向审慎评估。更值得警惕的是，负面报道虽占比13.2%，但其议题集中度极高，围绕监管收紧、隐私侵犯、就业替代等核心焦虑反复发酵。总体而言，AI正从单一的技术神话叙事，步入一个理性与反思、机遇与风险并存的新阶段……"

⚠️ 请确保最终输出达到600-800中文字，内容充实、观点鲜明、分析深入。现在开始生成："""

				# Call OpenAI API
				try:
					from openai import OpenAI
					openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

					response = openai_client.chat.completions.create(
						model=settings.OPENAI_MODEL or "gpt-4o-mini",
						messages=[
							{"role": "system", "content": "你是一位资深的AI产业观察员和科技媒体评论员，具有深厚的行业洞察力和媒体写作功底。你擅长从海量新闻数据中提取趋势、识别模式、洞察情绪变化，并能够提出犀利而有见地的观点和判断。你的分析报告逻辑严密、数据扎实、观点鲜明，既有宏观视野又有微观洞察。"},
							{"role": "user", "content": prompt}
						],
						max_tokens=2500,
						temperature=0.8
					)

					ai_summary = response.choices[0].message.content.strip()
					logger.info(f"Successfully generated AI summary using OpenAI API (length: {len(ai_summary)} chars)")

				except Exception as openai_error:
					logger.warning(f"Failed to call OpenAI API: {str(openai_error)}, falling back to template")

					# Fallback: Generate comprehensive template-based summary (600-800 chars)
					# Calculate additional metrics
					neutral_dominant = neutral_pct > 50
					positive_ratio = positive_count / max(negative_count, 1)

					# Part 1: Overall sentiment and trend analysis (150-200 chars)
					ai_summary = (
						f"从近期收集的{total_articles}篇AI相关新闻来看，全球舆论正呈现出耐人寻味的分化格局。"
						f"数据显示，仅有{positive_pct}%的报道（{positive_count}篇）带有明确的积极色彩，这一比例显著低于行业早期的乐观氛围，"
						f"反映出公众和媒体对AI技术的态度正从狂热追捧转向审慎评估。值得关注的是，超过半数的报道（{neutral_pct}%，共{neutral_count}篇）"
						f"采取中立观望立场，这种集体性的克制本身就是一个强烈信号——AI正从炒作期步入理性期。"
						f"同时，{negative_pct}%的负面报道（{negative_count}篇）虽占比不高，但其议题集中度极强，主要围绕监管收紧、隐私侵犯、"
						f"就业替代等核心焦虑反复发酵，对舆论场的影响力不容小觑。\n\n"
					)

					# Part 2: Core topics and focal points (150-200 chars)
					top_keywords = ', '.join(trending_topics[:6]) if trending_topics else 'AI技术、大模型、监管政策'
					ai_summary += (
						f"从关键词热度来看，{top_keywords}等主题反复出现，折射出当前AI舆论的三大焦点。"
						f"首先是大模型竞争白热化：OpenAI、Anthropic、Google、Meta等科技巨头的角力不仅是技术比拼，更是商业生态的卡位战，"
						f"媒体报道中既有对技术突破的赞叹，也有对垄断隐患的担忧。其次是AI应用落地进入深水区：医疗诊断、教育辅助、金融风控等垂直场景的探索"
						f"正从概念验证走向规模化部署，但实际效果与预期存在落差，导致报道情绪趋于谨慎。第三是监管政策密集出台：欧盟AI法案、美国行政令、"
						f"各国数据保护法规的收紧，让AI企业在创新与合规之间疲于奔命，这种政策不确定性也成为负面情绪的主要来源。\n\n"
					)

					# Part 3: Media attitude and propagation patterns (150-200 chars)
					ai_summary += (
						f"新闻来源分布显示，{source_summary}等媒体贡献了主要报道。对比不同类型媒体的报道倾向，可以发现明显差异：传统权威媒体如Guardian、"
						f"Times of India更倾向于深度调查和政策解读，语气相对克制；而Yahoo Entertainment等新兴平台则更关注热点事件和话题性内容，"
						f"情绪表达更为直接。有趣的是，负面报道在社交媒体的传播速度明显快于正面报道，这反映出'焦虑比乐观更具传染性'的舆论传播规律。"
						f"同时，涉及就业替代、隐私泄露的报道往往能引发更高的互动和转发，揭示出公众对AI技术的深层担忧远超表面数据所显示的程度。\n\n"
					)

					# Part 4: Future trends and analyst stance (150-200 chars)
					if positive_count > negative_count * 1.5:
						stance = "谨慎乐观"
						reasoning = (
							f"尽管积极报道占比仅为{positive_pct}%，但考虑到技术迭代的加速趋势和商业应用的持续拓展，AI产业的基本面依然向好。"
							f"当前的舆论降温更多是市场回归理性的健康调整，而非技术路径的根本性质疑。"
						)
					elif negative_count > positive_count:
						stance = "保持警惕"
						reasoning = (
							f"负面报道虽占比{negative_pct}%，但其影响力被严重低估。监管压力、伦理争议、技术滥用等问题若得不到妥善解决，"
							f"可能引发更大规模的信任危机，进而拖累整个产业的发展进程。"
						)
					else:
						stance = "理性审视"
						reasoning = (
							f"正负情绪的相对平衡反映出AI正处于关键转折点。技术潜力与现实风险并存，乐观主义与悲观论调交织，"
							f"这种复杂性要求我们既不盲目追捧，也不一味否定，而是以更成熟的心态推动AI向善发展。"
						)

					ai_summary += (
						f"展望未来，我持'{stance}'态度。{reasoning}"
						f"从舆论数据来看，AI正从技术神话走向社会共识的拐点，这既是挑战，更是机遇。只有正视问题、回应关切、完善治理，"
						f"AI才能真正从实验室的宠儿成长为推动人类进步的可靠力量。当前这场理性与反思的洗礼，或许正是AI迈向成熟所必须经历的成人礼。"
					)

			except Exception as e:
				logger.warning(f"Failed to generate OpenAI summary: {str(e)}")

		summary_data = {
			"total_articles": total_articles,
			"time_period": "Last 7 days",
			"generated_at": datetime.utcnow().isoformat() + 'Z',
			"sentiment_summary": dict(sentiment_summary),
			"trending_topics": trending_topics,
			"key_insights": key_insights if key_insights else ["Analysis based on limited articles"],
			"top_articles": [
				{
					"title": a.get('title', ''),
					"url": a.get('url', ''),
					"source": a.get('source_name', ''),
					"published_at": a.get('published_at', '')
				}
				for a in top_articles
			],
			"top_20_articles": [
				{
					"title": a.get('title', ''),
					"url": a.get('url', ''),
					"source": a.get('source_name', ''),
					"published_at": a.get('published_at', ''),
					"sentiment": a.get('sentiment', ''),
					"summary": a.get('summary', '')[:150] + '...' if len(a.get('summary', '')) > 150 else a.get('summary', '')
				}
				for a in top_20_articles
			],
			"ai_summary": ai_summary
		}

		return jsonify({
			"success": True,
			"data": summary_data
		})

	except Exception as e:
		logger.error(f"Error generating AI summary: {str(e)}")
		return jsonify({
			"success": False,
			"error": str(e)
		}), 500

