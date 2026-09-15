"""Initial Phase 2 schema migration creating all 14 AAE domain persistence tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-14 23:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    # 1. projects
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_projects_name", "projects", ["name"])

    # 2. requirements
    op.create_table(
        "requirements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_request", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="user"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("assumptions", JSONType, nullable=False),
        sa.Column("ambiguities", JSONType, nullable=False),
        sa.Column("conflicts", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_requirements_project_id", "requirements", ["project_id"])

    # 3. requirement_items
    op.create_table(
        "requirement_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", sa.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(50), nullable=False),
        sa.Column("risk", sa.String(50), nullable=False, server_default="LOW"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("idx_requirement_items_req_id", "requirement_items", ["requirement_id"])

    # 4. specifications
    op.create_table(
        "specifications",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requirement_id", sa.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("current_version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_specifications_project_id", "specifications", ["project_id"])
    op.create_index("idx_specifications_req_id", "specifications", ["requirement_id"])

    # 5. specification_versions
    op.create_table(
        "specification_versions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("specification_id", sa.UUID(as_uuid=True), sa.ForeignKey("specifications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("structured_content", JSONType, nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("specification_id", "version_number", name="uq_specification_versions_number"),
    )
    op.create_index("idx_spec_versions_lookup", "specification_versions", ["specification_id", "version_number"])

    # 6. workflows (current_version_id FK deferred)
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False, server_default="development"),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("current_version_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_workflows_project_id", "workflows", ["project_id"])

    # 7. workflow_versions
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("specification_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("specification_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("definition", JSONType, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("change_reason", sa.Text(), nullable=False, server_default="Initial version"),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="agent"),
        sa.Column("provider_version_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_number"),
    )
    op.create_index("idx_wf_versions_lookup", "workflow_versions", ["workflow_id", "version_number"])

    # Add circular foreign key to workflows.current_version_id
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.create_foreign_key(
                "fk_workflows_current_version",
                "workflow_versions",
                ["current_version_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "fk_workflows_current_version",
            "workflows",
            "workflow_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        )

    # 8. executions (embedding ExecutionResult)
    op.create_table(
        "executions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflow_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="QUEUED"),
        sa.Column("trigger_type", sa.String(50), nullable=False, server_default="MANUAL"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("result_technical_status", sa.String(50), nullable=True),
        sa.Column("result_semantic_status", sa.String(50), nullable=True),
        sa.Column("result_duration_ms", sa.Float(), nullable=True),
        sa.Column("result_output_data", JSONType, nullable=True),
        sa.Column("result_error_message", sa.Text(), nullable=True),
        sa.Column("result_error_details", JSONType, nullable=True),
    )
    op.create_index("idx_executions_workflow", "executions", ["workflow_id", "workflow_version_id"])
    op.create_index("idx_executions_correlation_id", "executions", ["correlation_id"])

    # 9. approvals
    op.create_table(
        "approvals",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False, server_default="deploy"),
        sa.Column("environment", sa.String(50), nullable=True),
        sa.Column("decision", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_action_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
    )
    op.create_index("idx_approvals_target", "approvals", ["target_type", "target_id", "target_version", "status"])
    op.create_index("idx_approvals_status_expiry", "approvals", ["status", "expires_at"])

    # 10. deployments
    op.create_table(
        "deployments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflow_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("workflow_version_number", sa.Integer(), nullable=False),
        sa.Column("target_environment", sa.String(50), nullable=False),
        sa.Column("deployed_by", sa.String(255), nullable=False),
        sa.Column("approval_id", sa.UUID(as_uuid=True), sa.ForeignKey("approvals.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("idx_deployments_workflow", "deployments", ["workflow_id", "workflow_version_id"])

    # 11. failure_records
    op.create_table(
        "failure_records",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", sa.UUID(as_uuid=True), sa.ForeignKey("executions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("failed_component", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("technical_details", JSONType, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_failure_records_execution", "failure_records", ["execution_id"])

    # 12. diagnostic_findings
    op.create_table(
        "diagnostic_findings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("failure_id", sa.UUID(as_uuid=True), sa.ForeignKey("failure_records.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("likely_cause", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(50), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_diagnostic_findings_failure", "diagnostic_findings", ["failure_id"])

    # 13. repair_attempts
    op.create_table(
        "repair_attempts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_version_number", sa.Integer(), nullable=False),
        sa.Column("failure_id", sa.UUID(as_uuid=True), sa.ForeignKey("failure_records.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("diagnostic_id", sa.UUID(as_uuid=True), sa.ForeignKey("diagnostic_findings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposed_change", JSONType, nullable=False),
        sa.Column("risk", sa.String(50), nullable=False, server_default="LOW"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PROPOSED"),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_repair_attempts_workflow", "repair_attempts", ["workflow_id"])

    # 14. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=False, server_default="SUCCESS"),
        sa.Column("metadata", JSONType, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("idx_audit_events_target", "audit_events", ["target_type", "target_id"])
    op.create_index("idx_audit_events_correlation", "audit_events", ["correlation_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("audit_events")
    op.drop_table("repair_attempts")
    op.drop_table("diagnostic_findings")
    op.drop_table("failure_records")
    op.drop_table("deployments")
    op.drop_table("approvals")
    op.drop_table("executions")

    # Drop circular FK before dropping tables
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("workflows") as batch_op:
            try:
                batch_op.drop_constraint("fk_workflows_current_version", type_="foreignkey")
            except Exception:
                pass
    else:
        try:
            op.drop_constraint("fk_workflows_current_version", "workflows", type_="foreignkey")
        except Exception:
            pass

    op.drop_table("workflow_versions")
    op.drop_table("workflows")
    op.drop_table("specification_versions")
    op.drop_table("specifications")
    op.drop_table("requirement_items")
    op.drop_table("requirements")
    op.drop_table("projects")
