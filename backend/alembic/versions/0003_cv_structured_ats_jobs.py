"""add structured CV + ATS + job salary fields

Revision ID: 0003_cv_structured
Revises: 0002_add_cv
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_cv_structured'
down_revision = '0002_add_cv'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.add_column(sa.Column('extraction_method', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('structured_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ats_score', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ats_issues', sa.Text(), nullable=True))

    with op.batch_alter_table('job_postings') as batch_op:
        batch_op.add_column(sa.Column('salary_min', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('salary_max', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('salary_raw', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('external_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('job_postings') as batch_op:
        batch_op.drop_column('source')
        batch_op.drop_column('external_id')
        batch_op.drop_column('salary_raw')
        batch_op.drop_column('salary_max')
        batch_op.drop_column('salary_min')

    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.drop_column('ats_issues')
        batch_op.drop_column('ats_score')
        batch_op.drop_column('structured_data')
        batch_op.drop_column('error_message')
        batch_op.drop_column('extraction_method')
