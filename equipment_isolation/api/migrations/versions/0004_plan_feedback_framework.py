"""Generalize correction requests into typed plan feedback.

Revision ID: 0004_plan_feedback_framework
Revises: 0003_scoped_asset_identity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_plan_feedback_framework"
down_revision = "0003_scoped_asset_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("change_request", "plan_feedback")
    op.alter_column("plan_feedback", "change_id", new_column_name="feedback_id")
    op.alter_column("plan_feedback", "change_type", new_column_name="feedback_type")
    op.execute("ALTER INDEX change_request_plan_state_idx RENAME TO plan_feedback_plan_state_idx")
    op.execute(
        "ALTER TABLE plan_feedback RENAME CONSTRAINT change_request_state_check "
        "TO plan_feedback_state_check"
    )

    op.add_column("plan_feedback", sa.Column("feedback_category", sa.Text(), nullable=True))
    op.add_column("plan_feedback", sa.Column("source_system", sa.Text()))
    op.add_column(
        "plan_feedback",
        sa.Column(
            "source_reference",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "plan_feedback",
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "plan_feedback",
        sa.Column("supersedes_feedback_id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        """
        UPDATE plan_feedback
        SET feedback_category = CASE
            WHEN feedback_type IN ('correct_label', 'mark_point_unavailable', 'mark_point_available')
                THEN 'input_correction'
            WHEN feedback_type IN (
                'accept_manual_candidate', 'reject_manual_candidate',
                'confirm_bypass', 'add_manual_isolation_point'
            )
                THEN 'manual_observation'
            ELSE NULL
        END
        """
    )
    op.alter_column("plan_feedback", "feedback_category", nullable=False)
    op.create_check_constraint(
        "plan_feedback_category_check",
        "plan_feedback",
        "feedback_category IN ('input_correction','requirement_deviation','manual_observation','execution_failure')",
    )
    op.create_foreign_key(
        "plan_feedback_supersedes_feedback_id_fkey",
        "plan_feedback",
        "plan_feedback",
        ["supersedes_feedback_id"],
        ["feedback_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "plan_feedback_category_state_idx",
        "plan_feedback",
        ["plan_id", "feedback_category", "state", sa.text("created_at DESC")],
    )

    op.rename_table("derivation_manifest_change", "derivation_manifest_feedback")
    op.alter_column("derivation_manifest_feedback", "change_id", new_column_name="feedback_id")
    op.rename_table("plan_version_change", "plan_version_feedback")
    op.alter_column("plan_version_feedback", "change_id", new_column_name="feedback_id")
    op.rename_table("change_coverage_result", "feedback_application_result")
    op.alter_column("feedback_application_result", "coverage_result_id", new_column_name="application_result_id")
    op.alter_column("feedback_application_result", "change_id", new_column_name="feedback_id")
    op.execute(
        "ALTER TABLE feedback_application_result RENAME CONSTRAINT "
        "change_coverage_manifest_change_key TO feedback_application_manifest_feedback_key"
    )

    op.create_table(
        "feedback_review_decision",
        sa.Column(
            "review_decision_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "feedback_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('approved','rejected')",
            name="feedback_review_decision_value_check",
        ),
    )
    op.create_index(
        "feedback_review_decision_feedback_idx",
        "feedback_review_decision",
        ["feedback_id", sa.text("created_at DESC")],
    )

    # Existing approval projections become their first append-only decisions.
    op.execute(
        """
        INSERT INTO feedback_review_decision (feedback_id, decision, actor_id, created_at)
        SELECT feedback_id, 'approved', approved_by, approved_at
        FROM plan_feedback
        WHERE approved_by IS NOT NULL AND approved_at IS NOT NULL
        """
    )


def downgrade():
    op.drop_index("feedback_review_decision_feedback_idx", table_name="feedback_review_decision")
    op.drop_table("feedback_review_decision")

    op.execute(
        "ALTER TABLE feedback_application_result RENAME CONSTRAINT "
        "feedback_application_manifest_feedback_key TO change_coverage_manifest_change_key"
    )
    op.alter_column("feedback_application_result", "feedback_id", new_column_name="change_id")
    op.alter_column("feedback_application_result", "application_result_id", new_column_name="coverage_result_id")
    op.rename_table("feedback_application_result", "change_coverage_result")
    op.alter_column("plan_version_feedback", "feedback_id", new_column_name="change_id")
    op.rename_table("plan_version_feedback", "plan_version_change")
    op.alter_column("derivation_manifest_feedback", "feedback_id", new_column_name="change_id")
    op.rename_table("derivation_manifest_feedback", "derivation_manifest_change")

    op.drop_index("plan_feedback_category_state_idx", table_name="plan_feedback")
    op.drop_constraint(
        "plan_feedback_supersedes_feedback_id_fkey",
        "plan_feedback",
        type_="foreignkey",
    )
    op.drop_constraint("plan_feedback_category_check", "plan_feedback", type_="check")
    for column in (
        "supersedes_feedback_id",
        "evidence",
        "source_reference",
        "source_system",
        "feedback_category",
    ):
        op.drop_column("plan_feedback", column)

    op.execute(
        "ALTER TABLE plan_feedback RENAME CONSTRAINT plan_feedback_state_check "
        "TO change_request_state_check"
    )
    op.execute("ALTER INDEX plan_feedback_plan_state_idx RENAME TO change_request_plan_state_idx")
    op.alter_column("plan_feedback", "feedback_type", new_column_name="change_type")
    op.alter_column("plan_feedback", "feedback_id", new_column_name="change_id")
    op.rename_table("plan_feedback", "change_request")
