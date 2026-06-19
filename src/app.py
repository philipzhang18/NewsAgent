from flask import Flask, render_template, jsonify, request
import logging
from datetime import datetime, timezone

from .api.news_api import news_api
from .api.visualization_api import visualization_bp
from .services.data_collection_service import data_collection_service
from .services.monitoring_service import monitoring_service
from .services.storage_service import storage_service, sqlite_storage
from .config.settings import settings
from .dash_app_enhanced import create_enhanced_dash_app
from .middleware.cors_middleware import init_cors
from .middleware.api_security import init_api_security
from .utils.async_helpers import run_async

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.secret_key = settings.FLASK_SECRET_KEY

    init_cors(
        app,
        origins=['http://localhost:*', 'http://127.0.0.1:*'],
        methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_credentials=True
    )
    init_api_security(app)

    app.register_blueprint(news_api, url_prefix='/api/news')
    app.register_blueprint(visualization_bp, url_prefix='/api/visualization')

    create_enhanced_dash_app(app)

    if not sqlite_storage.is_connected():
        storage_service.connect()

    @app.route('/')
    def index():
        return render_template('dashboard.html')

    @app.route('/home')
    def home():
        return render_template('index.html')

    @app.route('/articles')
    def articles_page():
        return render_template('articles.html')

    @app.route('/sources')
    def sources_page():
        return render_template('sources.html')

    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0",
            "storage": "sqlite",
        })

    @app.route('/api/monitoring/health', methods=['GET'])
    def monitoring_health():
        try:
            results = run_async(monitoring_service.run_health_checks())
            return jsonify({"success": True, "data": results})
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/monitoring/metrics', methods=['GET'])
    def monitoring_metrics():
        try:
            metrics = run_async(monitoring_service.collect_metrics())
            return jsonify({"success": True, "data": metrics})
        except Exception as e:
            logger.error(f"Metrics collection error: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/monitoring/status', methods=['GET'])
    def monitoring_status():
        try:
            status = monitoring_service.get_status()
            return jsonify({"success": True, "data": status})
        except Exception as e:
            logger.error(f"Status retrieval error: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/init', methods=['POST'])
    def initialize_service():
        try:
            async def _init():
                await data_collection_service.initialize()
                if not monitoring_service.is_running:
                    await monitoring_service.start()

            run_async(_init())
            return jsonify({
                "success": True,
                "message": "Service initialized successfully"
            })
        except Exception as e:
            logger.error(f"Error initializing service: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/start', methods=['POST'])
    def start_service():
        try:
            run_async(data_collection_service.initialize())
            started = data_collection_service.start_background_collection()
            if not monitoring_service.is_running:
                run_async(monitoring_service.start())
            return jsonify({
                "success": True,
                "message": "Service started successfully",
                "already_running": not started,
            })
        except Exception as e:
            logger.error(f"Error starting service: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/stop', methods=['POST'])
    def stop_service():
        try:
            data_collection_service.stop_background_collection()
            if monitoring_service.is_running:
                run_async(monitoring_service.stop())
            return jsonify({
                "success": True,
                "message": "Service stopped successfully"
            })
        except Exception as e:
            logger.error(f"Error stopping service: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/articles', methods=['GET'])
    def get_articles():
        try:
            limit = min(int(request.args.get('limit', 50)), 500)
            offset = int(request.args.get('offset', 0))
            articles = run_async(sqlite_storage.get_articles(limit=limit, offset=offset))
            return jsonify({
                "success": True,
                "articles": articles,
                "count": len(articles),
                "source": "sqlite",
            })
        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        try:
            stats = run_async(sqlite_storage.get_statistics())
            today = run_async(sqlite_storage.count_articles_today())
            sentiment = stats.get("articles_by_sentiment", {})
            return jsonify({
                "success": True,
                "stats": {
                    "total_articles": stats.get("total_articles", 0),
                    "today_articles": today,
                    "positive_articles": sentiment.get("positive", 0),
                    "negative_articles": sentiment.get("negative", 0),
                    "neutral_articles": sentiment.get("neutral", 0),
                    "articles_by_source": stats.get("articles_by_source", {}),
                    "database_size": stats.get("database_size", 0),
                }
            })
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/sources', methods=['GET', 'POST'])
    @app.route('/api/sources/<source_id>', methods=['GET', 'PUT', 'DELETE'])
    @app.route('/api/sources/<source_id>/test', methods=['POST'])
    def sources_proxy(source_id=None):
        from .api.news_api import get_sources, get_source, create_source, update_source, delete_source, test_source

        try:
            if '/test' in request.path:
                return test_source(source_id)
            if source_id:
                if request.method == 'GET':
                    return get_source(source_id)
                if request.method == 'PUT':
                    return update_source(source_id)
                if request.method == 'DELETE':
                    return delete_source(source_id)
            else:
                if request.method == 'GET':
                    return get_sources()
                if request.method == 'POST':
                    return create_source()
            return jsonify({"success": False, "error": "Method not allowed"}), 405
        except Exception as e:
            logger.error(f"Error proxying sources request: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == '__main__':
    if not settings.validate():
        logger.error("Invalid configuration. Please check your environment variables.")
        exit(1)

    logger.info("Starting News Agent application...")
    app.run(host='0.0.0.0', port=5000, debug=settings.DEBUG)
