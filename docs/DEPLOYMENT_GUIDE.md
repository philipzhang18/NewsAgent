# Production Deployment Guide

## Overview

This guide covers deploying NewsAgent to a production environment using Nginx as a reverse proxy and Gunicorn as the WSGI HTTP server.

## Architecture

```
Internet → Nginx (443/80) → Gunicorn (8000) → Flask Application
                          → Static Files
                          → Celery Workers
                          → Redis (6379)
                          → MongoDB (27017)
```

## Prerequisites

### System Requirements
- Linux server (Ubuntu 20.04+ recommended)
- Minimum 2 CPU cores
- Minimum 4GB RAM
- 20GB+ storage
- Root or sudo access

### Required Software
- Python 3.8+
- Nginx
- Redis
- MongoDB
- Git
- systemd

## Quick Deployment

### Automated Deployment

```bash
# Clone repository
git clone <your-repo-url> /var/www/newsagent
cd /var/www/newsagent

# Run deployment script
sudo chmod +x scripts/deploy.sh
sudo ./scripts/deploy.sh
```

The script will:
1. Install system dependencies
2. Create application directories
3. Set up Python virtual environment
4. Install Python packages
5. Configure Nginx
6. Set up systemd services
7. Start all services

### Manual Deployment

Follow these steps for manual deployment:

#### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    nginx redis-server mongodb \
    git supervisor
```

#### 2. Create Application User

```bash
sudo useradd -m -s /bin/bash newsagent
sudo usermod -aG www-data newsagent
```

#### 3. Set Up Application Directory

```bash
sudo mkdir -p /var/www/newsagent
sudo chown -R newsagent:www-data /var/www/newsagent
cd /var/www/newsagent
```

#### 4. Clone Repository

```bash
sudo -u newsagent git clone <your-repo-url> .
```

#### 5. Create Virtual Environment

```bash
sudo -u newsagent python3 -m venv venv
source venv/bin/activate
```

#### 6. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn gevent
```

#### 7. Configure Environment

```bash
cp env.example .env
nano .env  # Edit with your configuration
```

Required environment variables:
```env
FLASK_ENV=production
FLASK_SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-key
NEWS_API_KEY=your-news-api-key
MONGODB_URI=mongodb://localhost:27017/news_agent
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

#### 8. Set Permissions

```bash
sudo chown -R newsagent:www-data /var/www/newsagent
sudo chmod -R 755 /var/www/newsagent
```

#### 9. Create Log Directories

```bash
sudo mkdir -p /var/log/gunicorn /var/log/celery /var/log/newsagent
sudo mkdir -p /var/run/gunicorn /var/run/celery
sudo chown -R newsagent:www-data /var/log/gunicorn /var/log/celery /var/log/newsagent
sudo chown -R newsagent:www-data /var/run/gunicorn /var/run/celery
```

#### 10. Configure Nginx

```bash
sudo cp config/nginx/newsagent.conf /etc/nginx/sites-available/newsagent
sudo ln -s /etc/nginx/sites-available/newsagent /etc/nginx/sites-enabled/newsagent
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

#### 11. Install Systemd Services

```bash
sudo cp config/systemd/newsagent.service /etc/systemd/system/
sudo cp config/systemd/newsagent-celery-worker@.service /etc/systemd/system/
sudo cp config/systemd/newsagent-celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
```

#### 12. Enable and Start Services

```bash
# Enable services
sudo systemctl enable newsagent
sudo systemctl enable newsagent-celery-worker@collection
sudo systemctl enable newsagent-celery-worker@processing
sudo systemctl enable newsagent-celery-worker@default
sudo systemctl enable newsagent-celery-beat

# Start services
sudo systemctl start newsagent
sudo systemctl start newsagent-celery-worker@collection
sudo systemctl start newsagent-celery-worker@processing
sudo systemctl start newsagent-celery-worker@default
sudo systemctl start newsagent-celery-beat
```

## Configuration

### Gunicorn Configuration

Edit `gunicorn_config.py`:

```python
# Number of worker processes
workers = 4

# Worker class (use gevent for async)
worker_class = 'gevent'

# Bind address
bind = '127.0.0.1:8000'

# Timeouts
timeout = 120
keepalive = 5
```

### Nginx Configuration

Key settings in `config/nginx/newsagent.conf`:

- **SSL/TLS**: Configure certificates
- **Rate Limiting**: Adjust limits for your needs
- **Static Files**: Ensure correct paths
- **Upstream**: Configure backend servers

### Celery Workers

Configure worker queues by enabling/disabling services:

```bash
# Enable specific queues
sudo systemctl enable newsagent-celery-worker@collection
sudo systemctl enable newsagent-celery-worker@processing
sudo systemctl enable newsagent-celery-worker@analysis
sudo systemctl enable newsagent-celery-worker@storage
sudo systemctl enable newsagent-celery-worker@monitoring
sudo systemctl enable newsagent-celery-worker@default
```

## SSL/TLS Configuration

### Using Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d newsagent.example.com

# Auto-renewal is configured automatically
sudo certbot renew --dry-run
```

### Using Self-Signed Certificate (Development)

```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/newsagent.key \
    -out /etc/ssl/certs/newsagent.crt
```

## Service Management

### Application Service

```bash
# Start
sudo systemctl start newsagent

# Stop
sudo systemctl stop newsagent

# Restart
sudo systemctl restart newsagent

# Status
sudo systemctl status newsagent

# View logs
sudo journalctl -u newsagent -f
```

### Celery Workers

```bash
# Start all workers
sudo systemctl start newsagent-celery-worker@*

# Start specific worker
sudo systemctl start newsagent-celery-worker@collection

# Restart all workers
sudo systemctl restart newsagent-celery-worker@*

# View logs
sudo journalctl -u newsagent-celery-worker@collection -f
```

### Celery Beat

```bash
# Start
sudo systemctl start newsagent-celery-beat

# View logs
sudo journalctl -u newsagent-celery-beat -f
```

### Nginx

```bash
# Start
sudo systemctl start nginx

# Reload configuration
sudo systemctl reload nginx

# Test configuration
sudo nginx -t

# View access logs
sudo tail -f /var/log/nginx/newsagent_access.log

# View error logs
sudo tail -f /var/log/nginx/newsagent_error.log
```

## Monitoring

### Service Health

```bash
# Check all services
sudo systemctl status newsagent newsagent-celery-* nginx redis-server mongodb
```

### Application Logs

```bash
# Gunicorn logs
sudo tail -f /var/log/gunicorn/newsagent_access.log
sudo tail -f /var/log/gunicorn/newsagent_error.log

# Celery logs
sudo tail -f /var/log/celery/worker_collection.log
sudo tail -f /var/log/celery/beat.log

# Application logs
sudo tail -f /var/log/newsagent/app.log
```

### Resource Monitoring

```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Process monitoring
ps aux | grep gunicorn
ps aux | grep celery
```

### Flower (Celery Monitoring)

Access Flower web interface:
```
http://your-server-ip/flower/
```

## Backup and Recovery

### Database Backup

```bash
# MongoDB backup
mongodump --db news_agent --out /backup/mongodb/$(date +%Y%m%d)

# Redis backup (automatic via RDB)
# Configure in /etc/redis/redis.conf
```

### Application Backup

```bash
# Backup application files
tar -czf /backup/newsagent_$(date +%Y%m%d).tar.gz \
    /var/www/newsagent \
    --exclude='venv' \
    --exclude='__pycache__'
```

## Scaling

### Horizontal Scaling

1. **Add More Workers**:
   ```bash
   # Add more Celery workers
   sudo systemctl start newsagent-celery-worker@collection2
   sudo systemctl start newsagent-celery-worker@processing2
   ```

2. **Multiple Application Instances**:
   - Update Nginx upstream configuration
   - Run multiple Gunicorn instances on different ports
   - Use load balancer

3. **Database Scaling**:
   - Use MongoDB replica sets
   - Use Redis Sentinel for high availability

### Vertical Scaling

1. **Increase Workers**:
   Edit `gunicorn_config.py`:
   ```python
   workers = 8  # Increase based on CPU cores
   ```

2. **Increase Celery Concurrency**:
   Edit systemd service files:
   ```ini
   ExecStart=... -c 4  # Increase concurrency
   ```

## Security

### Firewall Configuration

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH (if needed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

### Application Security

1. **Change Default Secrets**: Update `FLASK_SECRET_KEY` in `.env`
2. **API Key Management**: Store sensitive keys securely
3. **Database Security**: Configure authentication
4. **Redis Security**: Enable password protection
5. **Regular Updates**: Keep system packages updated

## Troubleshooting

### Application Won't Start

```bash
# Check logs
sudo journalctl -u newsagent -n 50

# Check configuration
source /var/www/newsagent/venv/bin/activate
cd /var/www/newsagent
python -c "from src.app import app; print('OK')"
```

### Nginx Errors

```bash
# Test configuration
sudo nginx -t

# Check error log
sudo tail -f /var/log/nginx/error.log
```

### Worker Issues

```bash
# Check worker status
sudo systemctl status newsagent-celery-worker@collection

# View worker logs
sudo journalctl -u newsagent-celery-worker@collection -n 50
```

### Performance Issues

1. Check resource usage: `htop`, `iostat`
2. Monitor database queries
3. Check Redis memory usage: `redis-cli info memory`
4. Review application logs for slow operations

## Maintenance

### Regular Tasks

1. **Log Rotation**: Configure logrotate
2. **Database Cleanup**: Run cleanup tasks
3. **Security Updates**: `sudo apt-get update && sudo apt-get upgrade`
4. **Certificate Renewal**: Automated with Certbot
5. **Backup Verification**: Test backups regularly

### Updating Application

```bash
cd /var/www/newsagent
sudo -u newsagent git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart newsagent
sudo systemctl restart newsagent-celery-worker@*
```

## References

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Systemd Documentation](https://www.freedesktop.org/wiki/Software/systemd/)
- [Let's Encrypt](https://letsencrypt.org/)
