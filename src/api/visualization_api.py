"""
API endpoints for visualization data.
"""

import logging
import asyncio
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone, timedelta

from src.services.visualization_service import visualization_service
from src.middleware.api_security import require_rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
visualization_bp = Blueprint('visualization', __name__, url_prefix='/api/visualization')


def run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@visualization_bp.route('/sentiment/distribution', methods=['GET'])
@require_rate_limit
def get_sentiment_distribution():
    """
    Get sentiment distribution data.

    Query Parameters:
        days (int): Number of days to include (default: 7)

    Returns:
        JSON response with sentiment distribution
    """
    try:
        days = int(request.args.get('days', 7))

        fig = run_async(visualization_service.get_sentiment_distribution(days=days))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting sentiment distribution: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/sentiment/timeline', methods=['GET'])
@require_rate_limit
def get_sentiment_timeline():
    """
    Get sentiment timeline data.

    Query Parameters:
        days (int): Number of days to include (default: 30)

    Returns:
        JSON response with sentiment timeline
    """
    try:
        days = int(request.args.get('days', 30))

        fig = run_async(visualization_service.get_sentiment_timeline(days=days))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting sentiment timeline: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/sources/distribution', methods=['GET'])
@require_rate_limit
def get_source_distribution():
    """
    Get source distribution data.

    Query Parameters:
        days (int): Number of days to include (default: 7)

    Returns:
        JSON response with source distribution
    """
    try:
        days = int(request.args.get('days', 7))

        fig = run_async(visualization_service.get_source_distribution(days=days))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting source distribution: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/collection/trends', methods=['GET'])
@require_rate_limit
def get_collection_trends():
    """
    Get collection trends data.

    Query Parameters:
        days (int): Number of days to include (default: 30)

    Returns:
        JSON response with collection trends
    """
    try:
        days = int(request.args.get('days', 30))

        fig = run_async(visualization_service.get_collection_trends(days=days))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting collection trends: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/keywords/frequency', methods=['GET'])
@require_rate_limit
def get_keyword_frequency():
    """
    Get keyword frequency data.

    Query Parameters:
        days (int): Number of days to include (default: 7)
        top_n (int): Number of top keywords (default: 20)

    Returns:
        JSON response with keyword frequency
    """
    try:
        days = int(request.args.get('days', 7))
        top_n = int(request.args.get('top_n', 20))

        fig = run_async(visualization_service.get_keyword_frequency(days=days, top_n=top_n))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting keyword frequency: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/bias/distribution', methods=['GET'])
@require_rate_limit
def get_bias_distribution():
    """
    Get bias distribution data.

    Query Parameters:
        days (int): Number of days to include (default: 7)

    Returns:
        JSON response with bias distribution
    """
    try:
        days = int(request.args.get('days', 7))

        fig = run_async(visualization_service.get_bias_distribution(days=days))

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting bias distribution: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/processing/statistics', methods=['GET'])
@require_rate_limit
def get_processing_statistics():
    """
    Get processing statistics.

    Returns:
        JSON response with processing statistics
    """
    try:
        fig = run_async(visualization_service.get_processing_statistics())

        return jsonify({
            'success': True,
            'figure': fig.to_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting processing statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visualization_bp.route('/health', methods=['GET'])
def visualization_health():
    """
    Health check endpoint for visualization API.

    Returns:
        JSON response with health status
    """
    return jsonify({
        'success': True,
        'service': 'visualization_api',
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


def init_visualization_api(app):
    """
    Initialize visualization API with Flask app.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(visualization_bp)
    logger.info("Visualization API initialized")
