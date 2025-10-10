"""
API Security middleware for rate limiting and access control.
"""

import logging
import time
from functools import wraps
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

from flask import request, jsonify, g
from werkzeug.exceptions import TooManyRequests, Unauthorized, Forbidden

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per client
            requests_per_hour: Maximum requests per hour per client
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Storage for rate limit buckets
        # Format: {client_id: {'minute': [(timestamp, count)], 'hour': [(timestamp, count)]}}
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {'minute': [], 'hour': []})

        logger.info(f"Rate limiter initialized: {requests_per_minute}/min, {requests_per_hour}/hour")

    def _clean_old_entries(self, client_id: str):
        """Remove expired entries from buckets."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        # Clean minute bucket
        self.buckets[client_id]['minute'] = [
            (ts, count) for ts, count in self.buckets[client_id]['minute']
            if ts > minute_ago
        ]

        # Clean hour bucket
        self.buckets[client_id]['hour'] = [
            (ts, count) for ts, count in self.buckets[client_id]['hour']
            if ts > hour_ago
        ]

    def _get_request_count(self, client_id: str, window: str) -> int:
        """Get total request count in time window."""
        return sum(count for _, count in self.buckets[client_id][window])

    def check_rate_limit(self, client_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if request is within rate limits.

        Args:
            client_id: Unique identifier for the client

        Returns:
            Tuple of (is_allowed, error_message)
        """
        self._clean_old_entries(client_id)

        now = time.time()

        # Check minute limit
        minute_count = self._get_request_count(client_id, 'minute')
        if minute_count >= self.requests_per_minute:
            retry_after = 60 - (now - self.buckets[client_id]['minute'][0][0])
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute. Retry after {int(retry_after)}s"

        # Check hour limit
        hour_count = self._get_request_count(client_id, 'hour')
        if hour_count >= self.requests_per_hour:
            retry_after = 3600 - (now - self.buckets[client_id]['hour'][0][0])
            return False, f"Rate limit exceeded: {self.requests_per_hour} requests per hour. Retry after {int(retry_after)}s"

        # Record this request
        self.buckets[client_id]['minute'].append((now, 1))
        self.buckets[client_id]['hour'].append((now, 1))

        return True, None

    def get_rate_limit_info(self, client_id: str) -> Dict:
        """Get current rate limit status for client."""
        self._clean_old_entries(client_id)

        minute_count = self._get_request_count(client_id, 'minute')
        hour_count = self._get_request_count(client_id, 'hour')

        return {
            'minute': {
                'limit': self.requests_per_minute,
                'remaining': max(0, self.requests_per_minute - minute_count),
                'used': minute_count
            },
            'hour': {
                'limit': self.requests_per_hour,
                'remaining': max(0, self.requests_per_hour - hour_count),
                'used': hour_count
            }
        }


class APIKeyManager:
    """Manage API keys for access control."""

    def __init__(self):
        """Initialize API key manager."""
        # In production, this should be stored in database
        # Format: {api_key_hash: {'name': str, 'permissions': list, 'created_at': datetime}}
        self.api_keys: Dict[str, Dict] = {}
        self.enabled = False

        logger.info("API key manager initialized")

    def enable(self):
        """Enable API key authentication."""
        self.enabled = True
        logger.info("API key authentication enabled")

    def disable(self):
        """Disable API key authentication."""
        self.enabled = False
        logger.info("API key authentication disabled")

    def _hash_key(self, api_key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def create_api_key(self, name: str, permissions: list = None) -> str:
        """
        Create a new API key.

        Args:
            name: Name/identifier for the key
            permissions: List of allowed permissions

        Returns:
            Generated API key
        """
        import secrets

        # Generate random API key
        api_key = f"na_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(api_key)

        # Store key info
        self.api_keys[key_hash] = {
            'name': name,
            'permissions': permissions or ['read'],
            'created_at': datetime.now(),
            'last_used': None,
            'request_count': 0
        }

        logger.info(f"Created API key for: {name}")
        return api_key

    def validate_api_key(self, api_key: str) -> tuple[bool, Optional[Dict]]:
        """
        Validate an API key.

        Args:
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, key_info)
        """
        if not api_key:
            return False, None

        key_hash = self._hash_key(api_key)

        if key_hash not in self.api_keys:
            return False, None

        # Update last used
        key_info = self.api_keys[key_hash]
        key_info['last_used'] = datetime.now()
        key_info['request_count'] += 1

        return True, key_info

    def check_permission(self, api_key: str, required_permission: str) -> bool:
        """Check if API key has required permission."""
        is_valid, key_info = self.validate_api_key(api_key)

        if not is_valid:
            return False

        return required_permission in key_info['permissions'] or 'admin' in key_info['permissions']

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        key_hash = self._hash_key(api_key)

        if key_hash in self.api_keys:
            del self.api_keys[key_hash]
            logger.info("API key revoked")
            return True

        return False

    def list_api_keys(self) -> list:
        """List all API keys (without revealing actual keys)."""
        return [
            {
                'name': info['name'],
                'permissions': info['permissions'],
                'created_at': info['created_at'].isoformat(),
                'last_used': info['last_used'].isoformat() if info['last_used'] else None,
                'request_count': info['request_count']
            }
            for info in self.api_keys.values()
        ]


# Global instances
rate_limiter = RateLimiter(requests_per_minute=60, requests_per_hour=1000)
api_key_manager = APIKeyManager()


def get_client_id() -> str:
    """Get unique client identifier from request."""
    # Try API key first
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]

    # Fall back to IP address
    return request.remote_addr or 'unknown'


def require_rate_limit(func: Callable) -> Callable:
    """
    Decorator to enforce rate limiting on endpoint.

    Usage:
        @app.route('/api/endpoint')
        @require_rate_limit
        def endpoint():
            return {'data': 'value'}
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        client_id = get_client_id()

        # Check rate limit
        is_allowed, error_message = rate_limiter.check_rate_limit(client_id)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise TooManyRequests(error_message)

        # Add rate limit info to response headers
        g.rate_limit_info = rate_limiter.get_rate_limit_info(client_id)

        return func(*args, **kwargs)

    return wrapper


def require_api_key(permission: str = 'read') -> Callable:
    """
    Decorator to require API key authentication.

    Args:
        permission: Required permission level

    Usage:
        @app.route('/api/admin/endpoint')
        @require_api_key('admin')
        def admin_endpoint():
            return {'data': 'value'}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip if API key auth is disabled
            if not api_key_manager.enabled:
                return func(*args, **kwargs)

            # Get API key from header or query param
            api_key = request.headers.get('X-API-Key') or request.args.get('api_key')

            if not api_key:
                logger.warning("Missing API key")
                raise Unauthorized("API key required")

            # Validate API key
            is_valid, key_info = api_key_manager.validate_api_key(api_key)

            if not is_valid:
                logger.warning(f"Invalid API key attempted")
                raise Unauthorized("Invalid API key")

            # Check permission
            if not api_key_manager.check_permission(api_key, permission):
                logger.warning(f"Insufficient permissions: {key_info['name']}")
                raise Forbidden(f"Permission '{permission}' required")

            # Add key info to request context
            g.api_key_info = key_info

            return func(*args, **kwargs)

        return wrapper
    return decorator


def add_rate_limit_headers(response):
    """Add rate limit information to response headers."""
    if hasattr(g, 'rate_limit_info'):
        info = g.rate_limit_info
        response.headers['X-RateLimit-Limit-Minute'] = str(info['minute']['limit'])
        response.headers['X-RateLimit-Remaining-Minute'] = str(info['minute']['remaining'])
        response.headers['X-RateLimit-Limit-Hour'] = str(info['hour']['limit'])
        response.headers['X-RateLimit-Remaining-Hour'] = str(info['hour']['remaining'])

    return response


def init_api_security(app):
    """
    Initialize API security for Flask app.

    Args:
        app: Flask application instance
    """
    # Add after_request handler for rate limit headers
    app.after_request(add_rate_limit_headers)

    # Add error handlers
    @app.errorhandler(429)
    def handle_rate_limit_error(e):
        return jsonify({
            'success': False,
            'error': 'Rate limit exceeded',
            'message': str(e.description)
        }), 429

    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': str(e.description)
        }), 401

    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'message': str(e.description)
        }), 403

    # Add admin endpoints for API key management
    @app.route('/api/admin/keys', methods=['POST'])
    @require_api_key('admin')
    def create_api_key_endpoint():
        """Create a new API key."""
        data = request.get_json()
        name = data.get('name')
        permissions = data.get('permissions', ['read'])

        if not name:
            return jsonify({'success': False, 'error': 'Name required'}), 400

        api_key = api_key_manager.create_api_key(name, permissions)

        return jsonify({
            'success': True,
            'api_key': api_key,
            'message': 'API key created successfully'
        }), 201

    @app.route('/api/admin/keys', methods=['GET'])
    @require_api_key('admin')
    def list_api_keys_endpoint():
        """List all API keys."""
        keys = api_key_manager.list_api_keys()
        return jsonify({
            'success': True,
            'keys': keys
        })

    @app.route('/api/admin/keys/<key>', methods=['DELETE'])
    @require_api_key('admin')
    def revoke_api_key_endpoint(key):
        """Revoke an API key."""
        success = api_key_manager.revoke_api_key(key)

        if success:
            return jsonify({
                'success': True,
                'message': 'API key revoked'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'API key not found'
            }), 404

    logger.info("API security initialized")
