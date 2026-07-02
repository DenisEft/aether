#!/usr/bin/env bash
set -euo pipefail

# Initialize Let's Encrypt certificate for Aether
# Usage: DOMAIN=aether.example.com EMAIL=admin@example.com ./deploy/certbot-init.sh

: "${DOMAIN:?Set DOMAIN env var}"
: "${EMAIL:?Set EMAIL env var}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "Requesting certificate for ${DOMAIN}..."

# Create webroot for ACME challenge
sudo mkdir -p /var/www/certbot

# Run certbot in standalone mode first, then switch to nginx plugin
sudo certbot certonly --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --force-renewal

log "✅ Certificate obtained"

# Update nginx config with real domain
sudo sed -i "s/aether\.example\.com/${DOMAIN}/g" /etc/nginx/sites-available/aether.conf

# Test and reload
sudo nginx -t && sudo nginx -s reload

log "✅ Nginx configured with SSL"

# Setup auto-renewal cron
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'nginx -s reload'") | crontab -
    log "✅ Auto-renewal cron added (daily 3 AM)"
fi

log "Done! Aether is now available at https://${DOMAIN}"
