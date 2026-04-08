# Promo backend skeleton

Minimal foundation scaffold for the promo discount backend.

## Bootstrap

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
alembic upgrade head
promo-cli --help
```

## Layout

- `src/promo/` application package
- `migrations/` Alembic migrations
- `tests/` test contours

## Runtime Baseline

Target deploy contour:
- Ubuntu VPS
- PostgreSQL
- `nginx` as reverse proxy
- `systemd` service
- no Docker

Application entrypoint for the web service:

```bash
python -m promo.presentation
```

Before starting the service in production:

```bash
alembic upgrade head
```

Runtime expectations:
- `PROMO_STORAGE_ROOT` must be an absolute path
- `PROMO_WEB_AUTO_CREATE_SCHEMA=0` in production
- app binds to `127.0.0.1` and is published through `nginx`
- app logs go to `stdout/stderr` and are expected to be collected by `systemd-journald`

Deployment baseline artifacts:
- `deployment/env/promo.env.example`
- `deployment/systemd/promo.service`
- `deployment/nginx/promo.conf`
- `deployment/logrotate/promo`
- `deployment/scripts/prepare_runtime_dirs.sh`
- `deployment/scripts/runtime_smoke.sh`
- `deployment/scripts/release_readiness_check.sh`

## Release Readiness

Minimal repo-level release validation:

```bash
/tmp/promo-test-venv/bin/python -m pytest -q tests/unit/test_deployment_runtime_baseline.py tests/integration/test_release_readiness_baseline.py
```

Final repo-level acceptance proof:

```bash
PROMO_TEST_PYTHON=/tmp/promo-test-venv/bin/python deployment/scripts/final_acceptance_check.sh
```

Minimal deployment-oriented smoke against a running instance:

```bash
deployment/scripts/release_readiness_check.sh /etc/promo/promo.env
```
