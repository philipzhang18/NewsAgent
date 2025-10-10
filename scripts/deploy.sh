#!/bin/bash
# Production deployment script for NewsAgent

set -e  # Exit on error

echo "==================================="
echo "NewsAgent Production Deployment"
echo "==================================="

# Configuration
APP_NAME="newsagent"
APP_USER="www-data"
APP_GROUP="www-data"
APP_DIR="/var/www/${APP_NAME}"
VENV_DIR="${APP_DIR}/venv"
LOG_DIR="/var/log/${APP_NAME}"
RUN_DIR="/var/run/${APP_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

function print_error() {
    echo -e "${RED}✗ $1${NC}"
}

function print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

print_info "Starting deployment..."

# 1. Install system dependencies
print_info "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    redis-server \
    mongodb \
    git \
    supervisor
print_success "System dependencies installed"

# 2. Create application directory
print_info "Setting up application directory..."
mkdir -p ${APP_DIR}
mkdir -p ${LOG_DIR}
mkdir -p ${RUN_DIR}
mkdir -p ${RUN_DIR}/gunicorn
mkdir -p ${RUN_DIR}/celery
mkdir -p ${LOG_DIR}/gunicorn
mkdir -p ${LOG_DIR}/celery
print_success "Directories created"

# 3. Clone or update repository
print_info "Deploying application code..."
if [ -d "${APP_DIR}/.git" ]; then
    cd ${APP_DIR}
    git pull origin main
    print_success "Repository updated"
else
    git clone <YOUR_REPOSITORY_URL> ${APP_DIR}
    print_success "Repository cloned"
fi

# 4. Create virtual environment
print_info "Setting up Python virtual environment..."
cd ${APP_DIR}
python3 -m venv ${VENV_DIR}
source ${VENV_DIR}/bin/activate
print_success "Virtual environment created"

# 5. Install Python dependencies
print_info "Installing Python dependencies..."
${VENV_DIR}/bin/pip install --upgrade pip
${VENV_DIR}/bin/pip install -r requirements.txt
${VENV_DIR}/bin/pip install gunicorn gevent
print_success "Python dependencies installed"

# 6. Set up environment file
print_info "Configuring environment..."
if [ ! -f "${APP_DIR}/.env" ]; then
    cp ${APP_DIR}/env.example ${APP_DIR}/.env
    print_info "Created .env file from example. Please edit it with your settings."
    print_info "Edit: nano ${APP_DIR}/.env"
else
    print_success "Environment file exists"
fi

# 7. Set permissions
print_info "Setting permissions..."
chown -R ${APP_USER}:${APP_GROUP} ${APP_DIR}
chown -R ${APP_USER}:${APP_GROUP} ${LOG_DIR}
chown -R ${APP_USER}:${APP_GROUP} ${RUN_DIR}
chmod -R 755 ${APP_DIR}
print_success "Permissions set"

# 8. Configure Nginx
print_info "Configuring Nginx..."
cp ${APP_DIR}/config/nginx/newsagent.conf /etc/nginx/sites-available/${APP_NAME}
ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
rm -f /etc/nginx/sites-enabled/default
nginx -t
print_success "Nginx configured"

# 9. Configure systemd services
print_info "Installing systemd services..."
cp ${APP_DIR}/config/systemd/newsagent.service /etc/systemd/system/
cp ${APP_DIR}/config/systemd/newsagent-celery-worker@.service /etc/systemd/system/
cp ${APP_DIR}/config/systemd/newsagent-celery-beat.service /etc/systemd/system/
systemctl daemon-reload
print_success "Systemd services installed"

# 10. Enable and start services
print_info "Enabling services..."
systemctl enable newsagent
systemctl enable newsagent-celery-worker@collection
systemctl enable newsagent-celery-worker@processing
systemctl enable newsagent-celery-worker@default
systemctl enable newsagent-celery-beat
systemctl enable nginx
systemctl enable redis-server
systemctl enable mongodb
print_success "Services enabled"

# 11. Start services
print_info "Starting services..."
systemctl start redis-server
systemctl start mongodb
systemctl restart newsagent
systemctl restart newsagent-celery-worker@collection
systemctl restart newsagent-celery-worker@processing
systemctl restart newsagent-celery-worker@default
systemctl restart newsagent-celery-beat
systemctl restart nginx
print_success "Services started"

# 12. Check service status
print_info "Checking service status..."
echo ""
echo "Service Status:"
systemctl status newsagent --no-pager | head -n 3
systemctl status newsagent-celery-worker@collection --no-pager | head -n 3
systemctl status nginx --no-pager | head -n 3

# 13. Display useful information
echo ""
echo "==================================="
echo "Deployment Complete!"
echo "==================================="
echo ""
echo "Application URL: http://$(hostname -I | awk '{print $1}')"
echo "Dashboard URL: http://$(hostname -I | awk '{print $1}')/dashboard/"
echo ""
echo "Useful Commands:"
echo "  View app logs:     journalctl -u newsagent -f"
echo "  View worker logs:  journalctl -u newsagent-celery-worker@collection -f"
echo "  View nginx logs:   tail -f /var/log/nginx/newsagent_access.log"
echo "  Restart app:       sudo systemctl restart newsagent"
echo "  Restart workers:   sudo systemctl restart newsagent-celery-worker@*"
echo "  Check status:      sudo systemctl status newsagent"
echo ""
echo "Next Steps:"
echo "  1. Edit ${APP_DIR}/.env with your configuration"
echo "  2. Configure SSL certificate in /etc/nginx/sites-available/${APP_NAME}"
echo "  3. Update server_name in Nginx config"
echo "  4. Restart services after configuration changes"
echo ""

print_success "Deployment successful!"
