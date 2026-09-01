"""Add users.password_hash for SkillBridge auth."""

from alembic import op
import sqlalchemy as sa

revision = '0005_user_password_hash'
down_revision = '0004_interview_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('password_hash')
