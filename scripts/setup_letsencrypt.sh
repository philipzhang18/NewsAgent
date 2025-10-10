#!/bin/bash
# Setup Let's Encrypt SSL certificate with automatic renewal

set -e

# Configuration
DOMAIN="${1}"
EMAIL="${2}"
WEB_ROOT="/var/www/newsagent"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if domain is provided
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Error: Domain name required${NC}"
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 newsagent.example.com admin@example.com"
    exit 1
fi

# Check if email is provided
if [ -z "$EMAIL" ]; then
    echo -e "${RED}Error: Email address required${NC}"
    echo "Usage: $0 <domain> <email>"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}Setting up Let's Encrypt SSL for ${DOMAIN}${NC}"

# Install Certbot if not already installed
if ! command -v certbot &> /dev/null; then
    echo "Installing Certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
    echo -e "${GREEN}✓ Certbot installed${NC}"
fi

# Obtain certificate
echo "Obtaining SSL certificate..."
certbot --nginx \
    -d "${DOMAIN}" \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    --redirect

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SSL certificate obtained successfully${NC}"
else
    echo -e "${RED}✗ Failed to obtain SSL certificate${NC}"
    exit 1
fi

# Set up automatic renewal
echo "Setting up automatic renewal..."

# Create renewal hook script
cat > /etc/letsencrypt/renewal-hooks/post/restart-services.sh << 'EOF'
#!/bin/bash
# Restart services after certificate renewal

systemctl reload nginx
systemctl restart newsagent

echo "Services restarted after certificate renewal"
EOF

chmod +x /etc/letsencrypt/renewal-hooks/post/restart-services.sh

# Test renewal process
echo "Testing certificate renewal..."
certbot renew --dry-run

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Certificate renewal test successful${NC}"
else
    echo -e "${YELLOW}⚠ Certificate renewal test failed${NC}"
fi

# Display certificate information
echo ""
echo -e "${GREEN}SSL Certificate Information:${NC}"
certbot certificates -d "${DOMAIN}"

echo ""
echo -e "${GREEN}Setup Complete!${NC}"
echo ""
echo "Certificate Location: /etc/letsencrypt/live/${DOMAIN}/"
echo "Auto-renewal: Enabled (via systemd timer)"
echo ""
echo "To manually renew: sudo certbot renew"
echo "To check renewal status: sudo certbot certificates"
echo ""
echo "Note: Certificates will auto-renew 30 days before expiration"
