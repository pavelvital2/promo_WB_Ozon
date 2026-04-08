#!/usr/bin/env bash
set -eu

ENV_FILE="${1:-/etc/promo/promo.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "env file not found: $ENV_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

: "${PROMO_STORAGE_ROOT:?PROMO_STORAGE_ROOT is required}"
: "${PROMO_WEB_HOST:?PROMO_WEB_HOST is required}"
: "${PROMO_WEB_PORT:?PROMO_WEB_PORT is required}"

test -d "$PROMO_STORAGE_ROOT/uploads/tmp"
test -d "$PROMO_STORAGE_ROOT/runs"

curl --fail --silent --show-error "http://${PROMO_WEB_HOST}:${PROMO_WEB_PORT}/health" >/dev/null
