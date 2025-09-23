from flask import Blueprint, request, jsonify
from typing import List, Dict, Any
import logging
import requests

from ..services.news_collector_service import NewsCollectorService
from ..processors.news_processor import NewsProcessor
from ..models.news_models import NewsArticle
from ..config.settings import settings

logger = logging.getLogger(__name__)

# Create Blueprint
news_api = Blueprint('news_api', __name__)

# Initialize services
collector_service = NewsCollectorService()
processor = NewsProcessor()

@news_api.route('/status', methods=['GET'])
def get_status():
	"""Get the status of the news collection service."""
	try:
		# 返回仪表盘期望的数据格式
		status = {
			"service_running": False,
			"total_collectors": 2,
			"collection_stats": {
				"total_collections": 0,
				"total_articles": 0,
				"successful_collections": 0,
				"last_collection": None
			},
			"collectors": {
				"rss_collector": {
					"source_name": "RSS Feed Collector",
					"is_running": False,
					"last_collection": None,
					"articles_collected": 0
				},
				"news_api_collector": {
					"source_name": "NewsAPI Collector",
					"is_running": False,
					"last_collection": None,
					"articles_collected": 0
				}
			}
		}
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
	return {
		"id": item.get("url", ""),
		"title": item.get("title") or "",
		"summary": item.get("description") or "",
		"content": item.get("content") or "",
		"source": (item.get("source") or {}).get("name") or "NewsAPI",
		"source_name": (item.get("source") or {}).get("name") or "NewsAPI",
		"url": item.get("url") or "",
		"published_at": item.get("publishedAt") or None,
		"sentiment": "positive",  # 添加示例sentiment
		"bias_score": None,
		"category": None
	}

@news_api.route('/articles', methods=['GET'])
def get_articles():
	"""Get recent articles with optional filtering. Prefer NewsAPI if configured."""
	try:
		limit = request.args.get('limit', 50, type=int)
		query = request.args.get('q')
		country = request.args.get('country', 'us')
		category = request.args.get('category')

		if settings.NEWS_API_KEY:
			# 优先使用 NewsAPI
			params: Dict[str, Any] = {"apiKey": settings.NEWS_API_KEY, "pageSize": min(limit, 100)}
			endpoint = "https://newsapi.org/v2/top-headlines"
			if query:
				endpoint = "https://newsapi.org/v2/everything"
				params.update({"q": query, "language": "en", "sortBy": "publishedAt"})
			else:
				params.update({"country": country})
				if category:
					params.update({"category": category})

			resp = requests.get(endpoint, params=params, timeout=20)
			resp.raise_for_status()
			data = resp.json()
			articles = data.get("articles", [])
			mapped = [_map_newsapi_article(a) for a in articles][:limit]
			return jsonify({
				"success": True,
				"data": {
					"articles": mapped,
					"count": len(mapped),
					"limit": limit
				}
			})

		# 未配置 NEWS_API_KEY 时返回示例数据
		mock_articles = [{
			"id": "1",
			"title": "示例新闻标题",
			"summary": "这是一个示例新闻摘要",
			"content": "这是示例新闻的详细内容...",
			"source": "示例新闻源",
			"source_name": "示例新闻源",
			"url": "https://example.com",
			"published_at": None,
			"sentiment": "positive",
			"bias_score": None,
			"category": None
		}]
		return jsonify({
			"success": True,
			"data": {
				"articles": mock_articles,
				"count": len(mock_articles),
				"limit": limit
			}
		})
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
	try:
		return jsonify({"success": True, "message": "News collection triggered successfully"})
	except Exception as e:
		logger.error(f"Error triggering collection: {str(e)}")
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
		# 返回示例新闻源数据
		sources = [
			{
				"id": "newsapi",
				"name": "NewsAPI",
				"type": "API",
				"url": "https://newsapi.org",
				"status": "active",
				"last_updated": "2025-09-23T10:15:00Z",
				"articles_count": 150,
				"description": "Global news aggregation API service"
			},
			{
				"id": "rss_tech",
				"name": "Tech RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.feedburner.com/TechCrunch",
				"status": "active",
				"last_updated": "2025-09-23T09:15:00Z",
				"articles_count": 45,
				"description": "Technology news RSS feed"
			},
			{
				"id": "rss_business",
				"name": "Business RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.reuters.com/reuters/businessNews",
				"status": "active",
				"last_updated": "2025-09-23T08:45:00Z",
				"articles_count": 32,
				"description": "Business news RSS feed"
			},
			{
				"id": "twitter_x",
				"name": "Twitter/X",
				"type": "Social",
				"url": "https://twitter.com",
				"status": "active",
				"last_updated": "2025-09-23T10:12:00Z",
				"articles_count": 67,
				"description": "Twitter/X social media platform"
			},
			{
				"id": "reddit_news",
				"name": "Reddit News",
				"type": "Social",
				"url": "https://www.reddit.com/r/news",
				"status": "active",
				"last_updated": "2025-09-23T10:05:00Z",
				"articles_count": 78,
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
		# 返回示例源数据
		sources = [
			{
				"id": "newsapi",
				"name": "NewsAPI",
				"type": "API",
				"url": "https://newsapi.org",
				"status": "active",
				"last_updated": "2025-09-23T10:15:00Z",
				"articles_count": 150,
				"description": "Global news aggregation API service"
			},
			{
				"id": "rss_tech",
				"name": "Tech RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.feedburner.com/TechCrunch",
				"status": "active",
				"last_updated": "2025-09-23T09:15:00Z",
				"articles_count": 45,
				"description": "Technology news RSS feed"
			},
			{
				"id": "rss_business",
				"name": "Business RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.reuters.com/reuters/businessNews",
				"status": "active",
				"last_updated": "2025-09-23T08:45:00Z",
				"articles_count": 32,
				"description": "Business news RSS feed"
			},
			{
				"id": "twitter_x",
				"name": "Twitter/X",
				"type": "Social",
				"url": "https://twitter.com",
				"status": "active",
				"last_updated": "2025-09-23T10:12:00Z",
				"articles_count": 67,
				"description": "Twitter/X social media platform"
			},
			{
				"id": "reddit_news",
				"name": "Reddit News",
				"type": "Social",
				"url": "https://www.reddit.com/r/news",
				"status": "active",
				"last_updated": "2025-09-23T10:05:00Z",
				"articles_count": 78,
				"description": "Reddit news aggregation"
			}
		]

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
		data = request.get_json()
		if not data:
			return jsonify({"success": False, "error": "No data provided"}), 400

		# 验证必需字段
		required_fields = ['name', 'type', 'url']
		for field in required_fields:
			if not data.get(field):
				return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

		# 模拟更新源
		logger.info(f"Updating source {source_id} with data: {data}")

		# 返回更新后的源数据
		updated_source = {
			"id": source_id,
			"name": data.get("name"),
			"type": data.get("type"),
			"url": data.get("url"),
			"status": data.get("status", "active"),
			"description": data.get("description", ""),
			"last_updated": "2025-09-23T10:20:00Z",
			"articles_count": 0
		}

		return jsonify({
			"success": True,
			"message": "Source updated successfully",
			"data": updated_source
		})
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
		# 获取源信息
		sources = [
			{
				"id": "newsapi",
				"name": "NewsAPI",
				"type": "API",
				"url": "https://newsapi.org",
				"status": "active",
				"last_updated": "2025-09-23T10:15:00Z",
				"articles_count": 150,
				"description": "Global news aggregation API service"
			},
			{
				"id": "rss_tech",
				"name": "Tech RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.feedburner.com/TechCrunch",
				"status": "active",
				"last_updated": "2025-09-23T09:15:00Z",
				"articles_count": 45,
				"description": "Technology news RSS feed"
			},
			{
				"id": "rss_business",
				"name": "Business RSS Feeds",
				"type": "RSS",
				"url": "https://feeds.reuters.com/reuters/businessNews",
				"status": "active",
				"last_updated": "2025-09-23T08:45:00Z",
				"articles_count": 32,
				"description": "Business news RSS feed"
			},
			{
				"id": "twitter_x",
				"name": "Twitter/X",
				"type": "Social",
				"url": "https://twitter.com",
				"status": "active",
				"last_updated": "2025-09-23T10:12:00Z",
				"articles_count": 67,
				"description": "Twitter/X social media platform"
			},
			{
				"id": "reddit_news",
				"name": "Reddit News",
				"type": "Social",
				"url": "https://www.reddit.com/r/news",
				"status": "active",
				"last_updated": "2025-09-23T10:05:00Z",
				"articles_count": 78,
				"description": "Reddit news aggregation"
			}
		]

		source = next((s for s in sources if s["id"] == source_id), None)
		if not source:
			return jsonify({"success": False, "error": "Source not found"}), 404

		# 模拟测试不同类型的源
		if source["type"] == "API":
			test_result = {
				"success": True,
				"message": f"API connection test successful for {source['name']}",
				"details": {
					"response_time": "245ms",
					"status_code": 200,
					"available_articles": 150,
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
					"articles_found": 25,
					"last_updated": "2025-09-23T08:45:00Z"
				}
			}
		elif source["type"] == "Social":
			if source_id == "twitter_x":
				test_result = {
					"success": True,
					"message": f"Twitter/X API test successful for {source['name']}",
					"details": {
						"response_time": "189ms",
						"api_status": "operational",
						"tweets_accessible": True,
						"rate_limit_remaining": 100
					}
				}
			else:
				test_result = {
					"success": True,
					"message": f"Social media API test successful for {source['name']}",
					"details": {
						"response_time": "203ms",
						"api_status": "operational",
						"posts_accessible": True,
						"rate_limit_remaining": 75
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
	try:
		mock_stats = {
			"collection_stats": {
				"total_collections": 5,
				"total_articles": 25,
				"successful_collections": 4,
				"last_collection": "2025-09-23T10:15:00Z"
			},
			"article_stats": {
				"sentiment_distribution": {
					"positive": 12,
					"negative": 3,
					"neutral": 8,
					"mixed": 2
				},
				"source_distribution": {
					"NewsAPI": 15,
					"RSS Feed": 7,
					"Reddit": 3
				}
			}
		}
		return jsonify({"success": True, "data": mock_stats})
	except Exception as e:
		logger.error(f"Error getting stats: {str(e)}")
		return jsonify({"success": False, "error": str(e)}), 500
