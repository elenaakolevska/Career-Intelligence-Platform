"""add filename and status to cv_profiles

Revision ID: 0002_add_cv
Revises: 220081a56896
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_add_cv'
down_revision = '220081a56896'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.add_column(sa.Column('filename', sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'))


def downgrade() -> None:
    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.drop_column('status')
        batch_op.drop_column('filename')
