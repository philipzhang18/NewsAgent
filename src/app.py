from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import logging
import asyncio
from datetime import datetime

from .api.news_api import news_api
from .api.visualization_api import visualization_bp
from .services.news_collector_service import NewsCollectorService
from .services.monitoring_service import monitoring_service
from .config.settings import settings
from .dash_app_enhanced import create_enhanced_dash_app
from .middleware.cors_middleware import init_cors

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def run_async(coro):
    """Helper to run async functions in sync Flask context."""
    # In Flask sync context, there should be no running loop
    # Create a new event loop for this execution
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Keep the loop set for potential reuse in the same thread
        pass

def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.secret_key = settings.FLASK_SECRET_KEY
    
    # Initialize enhanced CORS with wildcard for local development
    init_cors(
        app,
        origins=['http://localhost:*', 'http://127.0.0.1:*'],
        methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_credentials=True
    )

    # Register blueprints
    app.register_blueprint(news_api, url_prefix='/api/news')
    app.register_blueprint(visualization_bp, url_prefix='/api/visualization')

    # Initialize enhanced Dash dashboard
    dash_app = create_enhanced_dash_app(app)

    # Initialize services
    collector_service = NewsCollectorService()
    
    @app.route('/')
    def index():
        """Main dashboard page with AI news statistics."""
        return render_template('dashboard.html')

    @app.route('/home')
    def home():
        """Original home page."""
        return render_template('index.html')
    
    @app.route('/articles')
    def articles_page():
        """Articles listing page."""
        return render_template('articles.html')
    
    @app.route('/sources')
    def sources_page():
        """Sources management page."""
        return render_template('sources.html')
    
    @app.route('/api/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        })

    @app.route('/api/monitoring/health', methods=['GET'])
    def monitoring_health():
        """Detailed health check with monitoring service."""
        try:
            results = run_async(monitoring_service.run_health_checks())
            return jsonify({
                "success": True,
                "data": results
            })
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/monitoring/metrics', methods=['GET'])
    def monitoring_metrics():
        """Get system metrics."""
        try:
            metrics = run_async(monitoring_service.collect_metrics())
            return jsonify({
                "success": True,
                "data": metrics
            })
        except Exception as e:
            logger.error(f"Metrics collection error: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/monitoring/status', methods=['GET'])
    def monitoring_status():
        """Get monitoring service status."""
        try:
            status = monitoring_service.get_status()
            return jsonify({
                "success": True,
                "data": status
            })
        except Exception as e:
            logger.error(f"Status retrieval error: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/init', methods=['POST'])
    def initialize_service():
        """Initialize the news collection service."""
        try:
            async def _init():
                await collector_service.initialize_collectors()
                await monitoring_service.start()

            run_async(_init())
            return jsonify({
                "success": True,
                "message": "Service initialized successfully"
            })
        except Exception as e:
            logger.error(f"Error initializing service: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/start', methods=['POST'])
    def start_service():
        """Start the news collection service."""
        try:
            async def _start():
                if not collector_service.is_running:
                    await collector_service.initialize_collectors()
                    # Start collection cycle in background
                    asyncio.create_task(collector_service.start_collection_cycle())
                if not monitoring_service.is_running:
                    await monitoring_service.start()

            run_async(_start())
            return jsonify({
                "success": True,
                "message": "Service started successfully"
            })
        except Exception as e:
            logger.error(f"Error starting service: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/stop', methods=['POST'])
    def stop_service():
        """Stop the news collection service."""
        try:
            async def _stop():
                if collector_service.is_running:
                    await collector_service.stop_collection_service()
                if monitoring_service.is_running:
                    await monitoring_service.stop()

            run_async(_stop())
            return jsonify({
                "success": True,
                "message": "Service stopped successfully"
            })
        except Exception as e:
            logger.error(f"Error stopping service: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # 添加与前端兼容的API端点
    @app.route('/api/articles', methods=['GET'])
    def get_articles():
        """Get articles for the main app."""
        try:
            # 重定向到news_api
            return jsonify({
                "success": True,
                "articles": []
            })
        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        """Get stats for the main app."""
        try:
            # 重定向到news_api
            return jsonify({
                "success": True,
                "stats": {
                    "total_articles": 0,
                    "today_articles": 0,
                    "positive_articles": 0,
                    "negative_articles": 0
                }
            })
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/sources', methods=['GET', 'POST'])
    @app.route('/api/sources/<source_id>', methods=['GET', 'PUT', 'DELETE'])
    @app.route('/api/sources/<source_id>/test', methods=['POST'])
    def sources_proxy(source_id=None):
        """Proxy /api/sources to /api/news/sources for compatibility."""
        from .api.news_api import get_sources, get_source, create_source, update_source, delete_source, test_source

        try:
            # Route to the appropriate handler
            if '/test' in request.path:
                return test_source(source_id)
            elif source_id:
                if request.method == 'GET':
                    return get_source(source_id)
                elif request.method == 'PUT':
                    return update_source(source_id)
                elif request.method == 'DELETE':
                    return delete_source(source_id)
            else:
                if request.method == 'GET':
                    return get_sources()
                elif request.method == 'POST':
                    return create_source()

            return jsonify({"success": False, "error": "Method not allowed"}), 405
        except Exception as e:
            logger.error(f"Error proxying sources request: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": "Endpoint not found"
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500
    
    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    # Validate settings
    if not settings.validate():
        logger.error("Invalid configuration. Please check your environment variables.")
        exit(1)
    
    logger.info("Starting News Agent application...")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=settings.DEBUG
    )
