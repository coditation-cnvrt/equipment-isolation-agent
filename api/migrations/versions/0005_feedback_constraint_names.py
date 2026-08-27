"""Align renamed feedback-table constraint names.

Revision ID: 0005_feedback_constraint_names
Revises: 0004_plan_feedback_framework
"""
from alembic import op


revision = "0005_feedback_constraint_names"
down_revision = "0004_plan_feedback_framework"
branch_labels = None
depends_on = None


RENAMES = (
    ("plan_feedback", "change_request_pkey", "plan_feedback_pkey"),
    (
        "plan_feedback",
        "change_request_plan_id_fkey",
        "plan_feedback_plan_id_fkey",
    ),
    (
        "plan_feedback",
        "change_request_raised_against_version_id_fkey",
        "plan_feedback_raised_against_version_id_fkey",
    ),
    (
        "derivation_manifest_feedback",
        "derivation_manifest_change_pkey",
        "derivation_manifest_feedback_pkey",
    ),
    (
        "derivation_manifest_feedback",
        "derivation_manifest_change_change_id_fkey",
        "derivation_manifest_feedback_feedback_id_fkey",
    ),
    (
        "derivation_manifest_feedback",
        "derivation_manifest_change_manifest_id_fkey",
        "derivation_manifest_feedback_manifest_id_fkey",
    ),
    (
        "plan_version_feedback",
        "plan_version_change_pkey",
        "plan_version_feedback_pkey",
    ),
    (
        "plan_version_feedback",
        "plan_version_change_change_id_fkey",
        "plan_version_feedback_feedback_id_fkey",
    ),
    (
        "plan_version_feedback",
        "plan_version_change_plan_version_id_fkey",
        "plan_version_feedback_plan_version_id_fkey",
    ),
    (
        "feedback_application_result",
        "change_coverage_result_pkey",
        "feedback_application_result_pkey",
    ),
    (
        "feedback_application_result",
        "change_coverage_result_change_id_fkey",
        "feedback_application_result_feedback_id_fkey",
    ),
    (
        "feedback_application_result",
        "change_coverage_result_manifest_id_fkey",
        "feedback_application_result_manifest_id_fkey",
    ),
)


def _rename(table: str, old_name: str, new_name: str) -> None:
    op.execute(
        f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
    )


def upgrade():
    for table, old_name, new_name in RENAMES:
        _rename(table, old_name, new_name)


def downgrade():
    for table, old_name, new_name in reversed(RENAMES):
        _rename(table, new_name, old_name)
