"""create models
Revision ID: 220081a56896
Revises: 0001_initial
Create Date: 2026-08-08 16:08:59.767467
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '220081a56896'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False))

    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.add_column(sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False))
        batch_op.create_foreign_key('cv_profiles_user_id_fkey', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cv_id', sa.Integer(), nullable=False),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_foreign_key('analysis_results_cv_id_fkey', 'analysis_results', 'cv_profiles', ['cv_id'], ['id'], ondelete='CASCADE')

    op.create_table(
        'interview_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('in_progress', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_foreign_key('interview_sessions_user_id_fkey', 'interview_sessions', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('interview_sessions_user_id_fkey', 'interview_sessions', type_='foreignkey')
    op.drop_table('interview_sessions')

    op.drop_constraint('analysis_results_cv_id_fkey', 'analysis_results', type_='foreignkey')
    op.drop_table('analysis_results')

    op.drop_table('job_postings')

    with op.batch_alter_table('cv_profiles') as batch_op:
        batch_op.drop_constraint('cv_profiles_user_id_fkey', type_='foreignkey')
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('updated_at')
