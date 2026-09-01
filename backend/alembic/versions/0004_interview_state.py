"""Add interview session state columns for P7-01 resume support."""

from alembic import op
import sqlalchemy as sa

revision = '0004_interview_state'
down_revision = '0003_cv_structured'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('interview_sessions') as batch_op:
        batch_op.add_column(sa.Column('cv_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('difficulty', sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending')
        )
        batch_op.add_column(sa.Column('history_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('running_score', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('overall_feedback', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('state_json', sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            'interview_sessions_cv_id_fkey',
            'cv_profiles',
            ['cv_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('interview_sessions') as batch_op:
        batch_op.drop_constraint('interview_sessions_cv_id_fkey', type_='foreignkey')
        batch_op.drop_column('state_json')
        batch_op.drop_column('overall_feedback')
        batch_op.drop_column('running_score')
        batch_op.drop_column('history_json')
        batch_op.drop_column('status')
        batch_op.drop_column('difficulty')
        batch_op.drop_column('cv_id')
