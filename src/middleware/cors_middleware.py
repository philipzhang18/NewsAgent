"""
Enhanced CORS (Cross-Origin Resource Sharing) configuration middleware.
"""

import logging
from functools import wraps
from flask import Flask, request, make_response, jsonify
from flask_cors import CORS
from typing import List, Optional, Dict
import re

logger = logging.getLogger(__name__)


class CORSConfig:
    """CORS configuration manager."""

    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_headers: Optional[List[str]] = None,
        expose_headers: Optional[List[str]] = None,
        max_age: int = 3600,
        allow_credentials: bool = True
    ):
        """
        Initialize CORS configuration.

        Args:
            allowed_origins: List of allowed origins (default: all)
            allowed_methods: List of allowed HTTP methods
            allowed_headers: List of allowed headers
            expose_headers: List of headers to expose to client
            max_age: Preflight cache duration in seconds
            allow_credentials: Allow credentials (cookies, auth)
        """
        self.allowed_origins = allowed_origins or ['*']
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH']
        self.allowed_headers = allowed_headers or ['Content-Type', 'Authorization', 'X-API-Key', 'X-Request-ID']
        self.expose_headers = expose_headers or ['X-RateLimit-Limit-Minute', 'X-RateLimit-Remaining-Minute']
        self.max_age = max_age
        self.allow_credentials = allow_credentials

        logger.info(f"CORS configured with origins: {self.allowed_origins}")

    def is_origin_allowed(self, origin: str) -> bool:
        """
        Check if origin is allowed.

        Args:
            origin: Origin to check

        Returns:
            True if allowed, False otherwise
        """
        if '*' in self.allowed_origins:
            return True

        if origin in self.allowed_origins:
            return True

        # Check wildcard patterns
        for allowed_origin in self.allowed_origins:
            if '*' in allowed_origin:
                pattern = allowed_origin.replace('*', '.*')
                if re.match(pattern, origin):
                    return True

        return False

    def get_cors_headers(self, origin: Optional[str] = None) -> Dict[str, str]:
        """
        Get CORS headers for response.

        Args:
            origin: Request origin

        Returns:
            Dictionary of CORS headers
        """
        headers = {}

        # Access-Control-Allow-Origin
        if origin and self.is_origin_allowed(origin):
            headers['Access-Control-Allow-Origin'] = origin
        elif '*' in self.allowed_origins:
            headers['Access-Control-Allow-Origin'] = '*'

        # Access-Control-Allow-Methods
        headers['Access-Control-Allow-Methods'] = ', '.join(self.allowed_methods)

        # Access-Control-Allow-Headers
        headers['Access-Control-Allow-Headers'] = ', '.join(self.allowed_headers)

        # Access-Control-Expose-Headers
        if self.expose_headers:
            headers['Access-Control-Expose-Headers'] = ', '.join(self.expose_headers)

        # Access-Control-Allow-Credentials
        if self.allow_credentials and origin != '*':
            headers['Access-Control-Allow-Credentials'] = 'true'

        # Access-Control-Max-Age
        headers['Access-Control-Max-Age'] = str(self.max_age)

        return headers


# Global CORS configuration
cors_config = CORSConfig()


def init_cors(
    app: Flask,
    origins: Optional[List[str]] = None,
    methods: Optional[List[str]] = None,
    allow_credentials: bool = True
):
    """
    Initialize CORS for Flask application.

    Args:
        app: Flask application instance
        origins: List of allowed origins
        methods: List of allowed HTTP methods
        allow_credentials: Allow credentials
    """
    global cors_config

    # Update configuration
    if origins:
        cors_config.allowed_origins = origins
    if methods:
        cors_config.allowed_methods = methods
    cors_config.allow_credentials = allow_credentials

    # Initialize Flask-CORS
    CORS(
        app,
        origins=cors_config.allowed_origins,
        methods=cors_config.allowed_methods,
        allow_headers=cors_config.allowed_headers,
        expose_headers=cors_config.expose_headers,
        max_age=cors_config.max_age,
        supports_credentials=cors_config.allow_credentials
    )

    # Add after_request handler for custom CORS headers
    @app.after_request
    def add_cors_headers(response):
        """Add CORS headers to response."""
        origin = request.headers.get('Origin')

        if origin and cors_config.is_origin_allowed(origin):
            headers = cors_config.get_cors_headers(origin)
            for key, value in headers.items():
                response.headers[key] = value

        return response

    # Add OPTIONS handler for preflight requests
    @app.before_request
    def handle_preflight():
        """Handle preflight OPTIONS requests."""
        if request.method == 'OPTIONS':
            origin = request.headers.get('Origin')

            if not origin or not cors_config.is_origin_allowed(origin):
                return jsonify({'error': 'Origin not allowed'}), 403

            response = make_response('', 204)
            headers = cors_config.get_cors_headers(origin)

            for key, value in headers.items():
                response.headers[key] = value

            return response

    logger.info("CORS initialized for Flask application")


def cors_enabled(origins: Optional[List[str]] = None):
    """
    Decorator to enable CORS for specific endpoints.

    Args:
        origins: List of allowed origins (overrides global config)

    Usage:
        @app.route('/api/endpoint')
        @cors_enabled(origins=['https://example.com'])
        def endpoint():
            return {'data': 'value'}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get request origin
            origin = request.headers.get('Origin')

            # Check if origin is allowed
            allowed_origins_list = origins if origins else cors_config.allowed_origins

            if origin and origin not in allowed_origins_list and '*' not in allowed_origins_list:
                return jsonify({'error': 'Origin not allowed'}), 403

            # Execute function
            response = make_response(func(*args, **kwargs))

            # Add CORS headers
            if origin:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'

            return response

        return wrapper
    return decorator


def require_secure_transport(func):
    """
    Decorator to require HTTPS for endpoints.

    Usage:
        @app.route('/api/secure-endpoint')
        @require_secure_transport
        def secure_endpoint():
            return {'data': 'value'}
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
            return jsonify({
                'success': False,
                'error': 'HTTPS required',
                'message': 'This endpoint requires a secure HTTPS connection'
            }), 403

        return func(*args, **kwargs)

    return wrapper
