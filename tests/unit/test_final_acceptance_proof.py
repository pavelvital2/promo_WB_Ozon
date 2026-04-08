from __future__ import annotations

from pathlib import Path


def test_final_acceptance_script_covers_required_repo_level_contours() -> None:
    script = Path("deployment/scripts/final_acceptance_check.sh").read_text(encoding="utf-8")

    assert "tests/smoke/test_package_imports.py" in script
    assert "tests/unit/test_admin_cli_bootstrap.py" in script
    assert "tests/smoke/test_admin_cli_first_admin.py" in script
    assert "tests/unit/test_auth_access_stores.py" in script
    assert "tests/unit/test_user_management_backend.py" in script
    assert "tests/unit/test_files_runs_async.py" in script
    assert "tests/integration/test_file_intake_validation.py" in script
    assert "tests/unit/test_workbook_safety_validation.py" in script
    assert "tests/integration/test_workbook_safety_boundary.py" in script
    assert "tests/unit/test_audit_history_logs_read_side.py" in script
    assert "tests/integration/test_db_side_read_models.py" in script
    assert "tests/integration/test_internal_ops_boundary.py" in script
    assert "tests/smoke/test_web_app_surface.py" in script
    assert "tests/unit/test_deployment_runtime_baseline.py" in script
    assert "tests/integration/test_release_readiness_baseline.py" in script


def test_readme_exposes_final_acceptance_proof_command() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "deployment/scripts/final_acceptance_check.sh" in readme
    assert "PROMO_TEST_PYTHON=/tmp/promo-test-venv/bin/python" in readme
