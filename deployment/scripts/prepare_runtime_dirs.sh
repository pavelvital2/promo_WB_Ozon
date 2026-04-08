#!/usr/bin/env bash
set -eu

: "${PROMO_STORAGE_ROOT:?PROMO_STORAGE_ROOT is required}"

case "$PROMO_STORAGE_ROOT" in
    /*) ;;
    *)
        echo "PROMO_STORAGE_ROOT must be an absolute path" >&2
        exit 1
        ;;
esac

install -d -m 0750 "$PROMO_STORAGE_ROOT"
install -d -m 0750 "$PROMO_STORAGE_ROOT/uploads"
install -d -m 0750 "$PROMO_STORAGE_ROOT/uploads/tmp"
install -d -m 0750 "$PROMO_STORAGE_ROOT/runs"
