"""Make data_quality_score nullable

Revision ID: 20261012_dq_nullable
Revises: b1a2c3d4e5f6
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20261012_dq_nullable'
down_revision = 'b1a2c3d4e5f6_prediction_engine_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Make data_quality_score nullable to distinguish None (unknown) from 0.0 (measured poor quality)."""
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # But for now, just document the schema change for PostgreSQL
    
    # For PostgreSQL:
    op.alter_column('prediction_versions', 'data_quality_score',
                    existing_type=sa.Float(),
                    nullable=True,
                    existing_server_default='0.0')
    
    # For SQLite, manual migration required:
    # 1. Create new table with nullable column
    # 2. Copy data
    # 3. Drop old table
    # 4. Rename new table


def downgrade():
    """Revert data_quality_score to NOT NULL."""
    op.alter_column('prediction_versions', 'data_quality_score',
                    existing_type=sa.Float(),
                    nullable=False,
                    existing_server_default='0.0')
