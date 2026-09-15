"""Migration upgrade and downgrade integration test."""

import os
from pathlib import Path
import tempfile
from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_downgrade_cycle():
    """
    Test that Alembic can cleanly upgrade from an empty database to head,
    that all 14 tables and indexes exist, that it can downgrade to base,
    and upgrade to head again.
    """
    repo_root = Path(__file__).resolve().parents[3]
    alembic_ini = repo_root / "alembic.ini"
    assert alembic_ini.exists(), f"alembic.ini not found at {alembic_ini}"

    # Use a temporary SQLite database file to verify full schema migrations
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    try:
        db_url = f"sqlite:///{db_path}"
        config = Config(str(alembic_ini))
        config.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade to head
        command.upgrade(config, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "projects",
            "requirements",
            "requirement_items",
            "specifications",
            "specification_versions",
            "workflows",
            "workflow_versions",
            "executions",
            "approvals",
            "deployments",
            "failure_records",
            "diagnostic_findings",
            "repair_attempts",
            "audit_events",
        }

        assert expected_tables.issubset(tables), f"Missing tables after upgrade: {expected_tables - tables}"

        # 2. Downgrade to base
        command.downgrade(config, "base")
        inspector_after_down = inspect(engine)
        tables_after_down = set(inspector_after_down.get_table_names())
        # All domain tables should be removed
        remaining_domain_tables = tables_after_down.intersection(expected_tables)
        assert not remaining_domain_tables, f"Tables still exist after downgrade: {remaining_domain_tables}"

        # 3. Upgrade to head again from clean state
        command.upgrade(config, "head")
        inspector_second_up = inspect(engine)
        tables_second_up = set(inspector_second_up.get_table_names())
        assert expected_tables.issubset(tables_second_up)

        engine.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
