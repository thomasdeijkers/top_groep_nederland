#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/opticore/projects/extern/top_groep_nederland"
SERVICE_FILE="/etc/systemd/system/top-groep-nederland.service"
NGINX_FILE="/etc/nginx/sites-available/tgn.opticore-insights.nl"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx rsync

mkdir -p "$APP_DIR/runtime/uploads" "$APP_DIR/runtime/logs" "$APP_DIR/runtime/exports"

sudo cp deploy/top-groep-nederland.service "$SERVICE_FILE"
sudo cp deploy/nginx-tgn.opticore-insights.nl.conf "$NGINX_FILE"
sudo ln -sf "$NGINX_FILE" /etc/nginx/sites-enabled/tgn.opticore-insights.nl

sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable top-groep-nederland
sudo systemctl reload nginx

echo "Server basis staat klaar. Plaats .env in $APP_DIR/.env en draai daarna de GitHub deploy."
