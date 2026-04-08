#!/usr/bin/env bash
set -eu

PYTHON_BIN="${PROMO_TEST_PYTHON:-python3}"

"$PYTHON_BIN" -m pytest -q \
  tests/smoke/test_package_imports.py \
  tests/unit/test_final_acceptance_proof.py \
  tests/unit/test_admin_cli_bootstrap.py \
  tests/smoke/test_admin_cli_first_admin.py \
  tests/unit/test_auth_access_stores.py \
  tests/unit/test_user_management_backend.py \
  tests/unit/test_files_runs_async.py \
  tests/integration/test_file_intake_validation.py \
  tests/unit/test_workbook_safety_validation.py \
  tests/integration/test_workbook_safety_boundary.py \
  tests/unit/test_audit_history_logs_read_side.py \
  tests/integration/test_db_side_read_models.py \
  tests/integration/test_internal_ops_boundary.py \
  tests/smoke/test_web_app_surface.py \
  tests/unit/test_deployment_runtime_baseline.py \
  tests/integration/test_release_readiness_baseline.py
