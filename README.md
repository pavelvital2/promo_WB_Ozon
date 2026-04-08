# Promo WB/Ozon

Веб-программа для расчёта скидок по Excel-файлам для `Wildberries` и `Ozon`.

Проект рассчитан на развёртывание на `Ubuntu VPS` с:
- `PostgreSQL`
- `nginx`
- `systemd`
- без Docker

## Что умеет

- аутентификация и роли доступа
- управление пользователями и магазинами
- загрузка входных файлов для `WB` и `Ozon`
- `check` и `process` сценарии для расчёта скидок
- история запусков, аудит, системные логи
- web UI и HTTP API
- release/deployment baseline для целевого VPS-контура

## Структура проекта

- `src/promo/` — код приложения
- `migrations/` — Alembic migrations
- `tests/` — unit / integration / smoke / acceptance контуры
- `deployment/` — артефакты развёртывания
- `docs/` — архитектурная и проектная документация

## Локальный запуск

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
alembic upgrade head
python -m promo.presentation
```

По умолчанию приложение поднимает HTTP surface. Для локальной разработки нужно задать окружение, как минимум:

- `PROMO_DATABASE_DSN`
- `PROMO_STORAGE_ROOT`

Пример dev-запуска:

```bash
PYTHONPATH=src \
PROMO_ENVIRONMENT=development \
PROMO_DATABASE_DSN=sqlite+pysqlite:////tmp/promo-dev.db \
PROMO_STORAGE_ROOT=/tmp/promo-storage \
PROMO_WEB_AUTO_CREATE_SCHEMA=1 \
PROMO_AUTONOMOUS_RUNTIME_ENABLED=1 \
PROMO_AUTONOMOUS_MAINTENANCE_ENABLED=1 \
python -m promo.presentation --host 127.0.0.1 --port 8000
```

## CLI

CLI используется для bootstrap и административных операций.

```bash
promo-cli --help
```

Для создания первого администратора используется `admin_cli` контур проекта.

## Целевой production contour

Ожидаемый способ развёртывания:

- приложение слушает `127.0.0.1`
- наружу публикуется через `nginx`
- запускается как `systemd` service
- логи уходят в `stdout/stderr` и собираются через `journald`

Критичные runtime expectations:

- `PROMO_STORAGE_ROOT` должен быть абсолютным путём
- в production должно быть `PROMO_WEB_AUTO_CREATE_SCHEMA=0`
- перед стартом приложения должны быть применены миграции:

```bash
alembic upgrade head
```

## Артефакты развёртывания

Готовые файлы для VPS-контура:

- `deployment/env/promo.env.example`
- `deployment/systemd/promo.service`
- `deployment/nginx/promo.conf`
- `deployment/logrotate/promo`
- `deployment/scripts/prepare_runtime_dirs.sh`
- `deployment/scripts/runtime_smoke.sh`
- `deployment/scripts/release_readiness_check.sh`
- `deployment/scripts/final_acceptance_check.sh`

## Проверка готовности

Минимальная release-проверка на уровне репозитория:

```bash
/tmp/promo-test-venv/bin/python -m pytest -q \
  tests/unit/test_deployment_runtime_baseline.py \
  tests/integration/test_release_readiness_baseline.py
```

Полный финальный acceptance-proof:

```bash
PROMO_TEST_PYTHON=/tmp/promo-test-venv/bin/python \
deployment/scripts/final_acceptance_check.sh
```

Smoke-проверка уже запущенного инстанса:

```bash
deployment/scripts/release_readiness_check.sh /etc/promo/promo.env
```

## Документация

Ключевые документы:

- `docs/01_PROJECT_OVERVIEW_AND_AGENT_DOC_MAP.md`
- `docs/02_SYSTEM_ARCHITECTURE.md`
- `docs/09_UI_PAGES_AND_ROUTES.md`
- `docs/10_WB_PROCESSING_FLOW.md`
- `docs/11_OZON_PROCESSING_FLOW.md`
- `docs/21_FINAL_STATUS_HANDOFF_AFTER_R7_2026_04_07.md`

## Текущее состояние

Проект доведён до:

- полного MVP-контура по текущему roadmap
- web UI + HTTP API
- release-readiness baseline
- final acceptance proof

Дальнейшие шаги, если понадобятся, уже относятся не к незакрытому roadmap, а к следующему backlog:
- реальный production rollout
- browser E2E
- расширенный observability / operations contour
