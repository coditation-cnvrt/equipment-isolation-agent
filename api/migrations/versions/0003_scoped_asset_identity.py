"""Scope durable asset identities by UniGraph project or CNVRT drawing.

Revision ID: 0003_scoped_asset_identity
Revises: 0002_plan_corrections
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_scoped_asset_identity"
down_revision = "0002_plan_corrections"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("asset_reference", sa.Column("scope_key", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE asset_reference
        SET scope_key = CASE
            WHEN external_system LIKE '%unigraph%'
                 AND COALESCE(NULLIF(context->>'unigraph_project_id', ''), NULLIF(context->>'project_id', '')) IS NOT NULL
                THEN 'unigraph:' || COALESCE(NULLIF(context->>'unigraph_project_id', ''), NULLIF(context->>'project_id', ''))
            WHEN external_system LIKE '%hilt%' OR external_system LIKE '%drawing%'
                THEN 'cnvrt:' || COALESCE(NULLIF(context->>'cnvrt_project_id', ''), 'unknown')
                     || ':collection:' || COALESCE(NULLIF(context->>'collection_id', ''), 'unknown')
                     || ':job:' || COALESCE(NULLIF(context->>'job_id', ''), 'unknown')
            ELSE 'context:' || md5(context::text)
        END
        """
    )
    op.alter_column("asset_reference", "scope_key", nullable=False)
    op.drop_constraint("asset_reference_external_key", "asset_reference", type_="unique")
    op.create_unique_constraint(
        "asset_reference_scoped_external_key",
        "asset_reference",
        ["external_system", "scope_key", "external_id"],
    )


def downgrade():
    op.drop_constraint("asset_reference_scoped_external_key", "asset_reference", type_="unique")
    op.create_unique_constraint(
        "asset_reference_external_key",
        "asset_reference",
        ["external_system", "external_id"],
    )
    op.drop_column("asset_reference", "scope_key")
