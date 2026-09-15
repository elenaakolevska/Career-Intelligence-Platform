"""Add job_postings.external_id index to match models.py.

Revision ID: 0006_job_external_id_index
Revises: 0005_user_password_hash
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_job_external_id_index'
down_revision = '0005_user_password_hash'
branch_labels = None
depends_on = None


def _has_index() -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    names = {ix['name'] for ix in insp.get_indexes('job_postings')}
    return 'ix_job_postings_external_id' in names


def upgrade() -> None:
    if not _has_index():
        op.create_index('ix_job_postings_external_id', 'job_postings', ['external_id'])


def downgrade() -> None:
    if _has_index():
        op.drop_index('ix_job_postings_external_id', table_name='job_postings')
