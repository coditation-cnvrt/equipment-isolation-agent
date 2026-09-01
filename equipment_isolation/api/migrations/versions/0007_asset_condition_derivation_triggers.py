"""Record asset-condition derivation triggers.

Revision ID: 0007_asset_state_derivation
Revises: 0006_shared_asset_conditions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_asset_state_derivation"
down_revision = "0006_shared_asset_conditions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "derivation_manifest",
        sa.Column("trigger_kind", sa.Text(), server_default="corrections", nullable=False),
    )
    op.add_column(
        "derivation_manifest",
        sa.Column(
            "trigger_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        "trigger_kind IN ('corrections','asset_conditions','combined')",
    )


def downgrade():
    op.drop_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        type_="check",
    )
    op.drop_column("derivation_manifest", "trigger_snapshot")
    op.drop_column("derivation_manifest", "trigger_kind")
