#!/usr/bin/env bash
set -eu

ENV_FILE="${1:-/etc/promo/promo.env}"
SERVICE_FILE="${2:-deployment/systemd/promo.service}"
NGINX_FILE="${3:-deployment/nginx/promo.conf}"

if [ ! -f "$ENV_FILE" ]; then
    echo "env file not found: $ENV_FILE" >&2
    exit 1
fi

if [ ! -f "$SERVICE_FILE" ]; then
    echo "systemd service file not found: $SERVICE_FILE" >&2
    exit 1
fi

if [ ! -f "$NGINX_FILE" ]; then
    echo "nginx config file not found: $NGINX_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

: "${PROMO_ENVIRONMENT:?PROMO_ENVIRONMENT is required}"
: "${PROMO_STORAGE_ROOT:?PROMO_STORAGE_ROOT is required}"
: "${PROMO_WEB_HOST:?PROMO_WEB_HOST is required}"
: "${PROMO_WEB_PORT:?PROMO_WEB_PORT is required}"
: "${PROMO_WEB_AUTO_CREATE_SCHEMA:?PROMO_WEB_AUTO_CREATE_SCHEMA is required}"

case "$PROMO_STORAGE_ROOT" in
    /*) ;;
    *)
        echo "PROMO_STORAGE_ROOT must be an absolute path" >&2
        exit 1
        ;;
esac

if [ "$PROMO_ENVIRONMENT" != "production" ]; then
    echo "PROMO_ENVIRONMENT must be production for release readiness checks" >&2
    exit 1
fi

if [ "$PROMO_WEB_AUTO_CREATE_SCHEMA" != "0" ]; then
    echo "PROMO_WEB_AUTO_CREATE_SCHEMA must be 0 for release readiness checks" >&2
    exit 1
fi

grep -Fq "python -m promo.presentation" "$SERVICE_FILE"
grep -Eq "^EnvironmentFile=" "$SERVICE_FILE"
grep -Fq "proxy_pass http://${PROMO_WEB_HOST}:${PROMO_WEB_PORT};" "$NGINX_FILE"

"$(dirname "$0")/prepare_runtime_dirs.sh"
"$(dirname "$0")/runtime_smoke.sh" "$ENV_FILE"
