#!/bin/bash
# Generate self-signed SSL certificate for development/testing

set -e

# Configuration
DOMAIN="${1:-localhost}"
DAYS=365
KEY_SIZE=2048
CERT_DIR="./ssl"
CERT_FILE="${CERT_DIR}/${DOMAIN}.crt"
KEY_FILE="${CERT_DIR}/${DOMAIN}.key"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Generating self-signed SSL certificate for ${DOMAIN}${NC}"

# Create SSL directory if it doesn't exist
mkdir -p "${CERT_DIR}"

# Generate private key and certificate
openssl req -x509 \
    -nodes \
    -days ${DAYS} \
    -newkey rsa:${KEY_SIZE} \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1"

# Set permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo -e "${GREEN}✓ Certificate generated successfully${NC}"
echo ""
echo "Certificate: ${CERT_FILE}"
echo "Private Key: ${KEY_FILE}"
echo "Valid for: ${DAYS} days"
echo ""
echo "To use with Nginx, update your configuration:"
echo "  ssl_certificate ${CERT_FILE};"
echo "  ssl_certificate_key ${KEY_FILE};"
echo ""
echo "Note: This is a self-signed certificate for development only."
echo "For production, use Let's Encrypt or a trusted CA."
