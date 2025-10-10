# HTTPS and CORS Configuration Guide

## Overview

This guide covers configuring HTTPS (SSL/TLS) and CORS (Cross-Origin Resource Sharing) for secure communication and cross-origin access.

## HTTPS Configuration

### Why HTTPS?

HTTPS provides:
- **Encryption**: Protects data in transit
- **Authentication**: Verifies server identity
- **Integrity**: Prevents tampering
- **SEO**: Better search rankings
- **Trust**: Browser security indicators

### SSL/TLS Certificate Options

#### 1. Let's Encrypt (Recommended for Production)

Free, automated SSL certificates that auto-renew.

**Setup:**
```bash
sudo chmod +x scripts/setup_letsencrypt.sh
sudo ./scripts/setup_letsencrypt.sh newsagent.example.com admin@example.com
```

**Features:**
- Free certificates
- Automatic renewal every 90 days
- Trusted by all major browsers
- Easy setup with Certbot

**Manual Setup:**
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d newsagent.example.com

# Test renewal
sudo certbot renew --dry-run
```

#### 2. Self-Signed Certificate (Development Only)

For local development and testing.

**Generate:**
```bash
chmod +x scripts/generate_ssl_cert.sh
./scripts/generate_ssl_cert.sh localhost
```

**Output:**
- `ssl/localhost.crt` - Certificate file
- `ssl/localhost.key` - Private key file

**Note:** Browsers will show a warning for self-signed certificates.

#### 3. Commercial Certificate

For enterprise deployments.

1. Purchase certificate from CA (DigiCert, Comodo, etc.)
2. Generate CSR:
   ```bash
   openssl req -new -newkey rsa:2048 -nodes \
     -keyout newsagent.key \
     -out newsagent.csr
   ```
3. Submit CSR to CA
4. Receive and install certificate

### Nginx HTTPS Configuration

Update `config/nginx/newsagent.conf`:

```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name newsagent.example.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name newsagent.example.com;

    # SSL certificate (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/newsagent.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/newsagent.example.com/privkey.pem;

    # Or self-signed
    # ssl_certificate /path/to/ssl/newsagent.crt;
    # ssl_certificate_key /path/to/ssl/newsagent.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # ... rest of configuration
}
```

### Testing HTTPS

```bash
# Check certificate
openssl s_client -connect newsagent.example.com:443

# Test SSL configuration
curl -I https://newsagent.example.com

# SSL Labs test
https://www.ssllabs.com/ssltest/
```

## CORS Configuration

### Understanding CORS

CORS allows controlled access from different origins (domains).

**Same-Origin Policy** prevents:
```javascript
// On https://example.com
fetch('https://api.newsagent.com/data')  // Blocked by default
```

**CORS** enables:
- Cross-origin API access
- Controlled security
- Credentials sharing
- Custom headers

### Flask CORS Setup

#### Basic Configuration

```python
from flask import Flask
from src.middleware.cors_middleware import init_cors

app = Flask(__name__)

# Initialize CORS
init_cors(
    app,
    origins=['https://example.com', 'https://app.example.com'],
    methods=['GET', 'POST', 'PUT', 'DELETE'],
    allow_credentials=True
)
```

#### Advanced Configuration

```python
from src.middleware.cors_middleware import CORSConfig, init_cors

# Custom CORS configuration
cors_config = CORSConfig(
    allowed_origins=[
        'https://example.com',
        'https://*.example.com',  # Wildcard subdomain
        'http://localhost:3000'     # Development
    ],
    allowed_methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
    allowed_headers=['Content-Type', 'Authorization', 'X-API-Key'],
    expose_headers=['X-RateLimit-Limit', 'X-RateLimit-Remaining'],
    max_age=3600,  # Preflight cache (1 hour)
    allow_credentials=True
)

init_cors(app)
```

### Environment-Based Configuration

#### Development (.env)
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
CORS_ALLOW_CREDENTIALS=true
```

#### Production (.env)
```env
CORS_ORIGINS=https://newsagent.example.com,https://app.example.com
CORS_ALLOW_CREDENTIALS=true
```

#### Configuration Loading
```python
import os

origins = os.getenv('CORS_ORIGINS', '*').split(',')
allow_credentials = os.getenv('CORS_ALLOW_CREDENTIALS', 'true').lower() == 'true'

init_cors(
    app,
    origins=origins,
    allow_credentials=allow_credentials
)
```

### Per-Endpoint CORS

```python
from src.middleware.cors_middleware import cors_enabled

@app.route('/api/public')
@cors_enabled(origins=['*'])  # Allow all origins
def public_endpoint():
    return {'data': 'public'}

@app.route('/api/private')
@cors_enabled(origins=['https://app.example.com'])  # Specific origin
def private_endpoint():
    return {'data': 'private'}
```

### Requiring HTTPS

```python
from src.middleware.cors_middleware import require_secure_transport

@app.route('/api/secure-data')
@require_secure_transport
def secure_data():
    return {'sensitive': 'data'}
```

### CORS Headers Explained

#### Request Headers

```http
Origin: https://example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type, Authorization
```

#### Response Headers

```http
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Expose-Headers: X-RateLimit-Limit
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 3600
```

### Testing CORS

#### cURL Test

```bash
# Simple request
curl -H "Origin: https://example.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://newsagent.example.com/api/endpoint

# With credentials
curl -H "Origin: https://example.com" \
     -X GET \
     --cookie "session=abc123" \
     https://newsagent.example.com/api/data
```

#### JavaScript Test

```javascript
// Modern fetch with credentials
fetch('https://newsagent.example.com/api/data', {
  method: 'GET',
  credentials: 'include',  // Send cookies
  headers: {
    'Content-Type': 'application/json'
  }
})
.then(response => response.json())
.then(data => console.log(data));
```

#### Browser DevTools

1. Open browser DevTools (F12)
2. Go to Network tab
3. Make request to API
4. Check response headers for CORS headers

### Common Issues

#### 1. CORS Error: "No Access-Control-Allow-Origin header"

**Cause:** Origin not in allowed list

**Fix:**
```python
init_cors(app, origins=['https://your-frontend.com'])
```

#### 2. Credentials Not Sent

**Cause:** Credentials not enabled or wildcard origin

**Fix:**
```python
# Don't use wildcard with credentials
init_cors(
    app,
    origins=['https://specific-domain.com'],
    allow_credentials=True
)
```

```javascript
// Enable credentials in fetch
fetch(url, { credentials: 'include' })
```

#### 3. Custom Headers Blocked

**Cause:** Headers not in allowed list

**Fix:**
```python
cors_config.allowed_headers.append('X-Custom-Header')
```

#### 4. Preflight Request Failing

**Cause:** OPTIONS not handled or timeout

**Fix:**
```python
# Handled automatically by middleware
# Increase max_age to reduce preflight requests
cors_config.max_age = 86400  # 24 hours
```

### Security Best Practices

#### 1. Restrict Origins

```python
# ❌ Bad - Too permissive
origins = ['*']

# ✅ Good - Specific origins
origins = [
    'https://newsagent.example.com',
    'https://app.example.com'
]
```

#### 2. Validate Origin Dynamically

```python
def is_origin_allowed(origin):
    # Check against database or config
    allowed = get_allowed_origins_from_db()
    return origin in allowed
```

#### 3. Use HTTPS Only

```python
@app.before_request
def require_https():
    if not request.is_secure:
        return redirect(request.url.replace('http://', 'https://'))
```

#### 4. Set Appropriate Timeouts

```python
cors_config.max_age = 3600  # 1 hour, not too long
```

#### 5. Expose Only Needed Headers

```python
cors_config.expose_headers = [
    'X-RateLimit-Limit',
    'X-RateLimit-Remaining'
]
# Don't expose sensitive headers
```

### Production Checklist

- [ ] HTTPS enabled with valid certificate
- [ ] HTTP redirects to HTTPS
- [ ] HSTS header configured
- [ ] Specific CORS origins (no wildcards)
- [ ] Credentials enabled only if needed
- [ ] Custom headers documented
- [ ] Preflight cache configured
- [ ] Certificate auto-renewal setup
- [ ] SSL configuration tested (SSL Labs)
- [ ] CORS tested from all allowed origins

### Monitoring

#### Certificate Expiration

```bash
# Check expiration date
openssl x509 -in /path/to/cert.crt -noout -enddate

# Check with Certbot
sudo certbot certificates
```

#### CORS Logs

```python
import logging

@app.after_request
def log_cors(response):
    origin = request.headers.get('Origin')
    if origin:
        logger.info(f"CORS request from: {origin}")
    return response
```

### Docker Configuration

For Docker deployments, mount certificates:

```yaml
volumes:
  - ./ssl:/etc/nginx/ssl:ro
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

## References

- [CORS MDN Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [SSL Labs Server Test](https://www.ssllabs.com/ssltest/)
