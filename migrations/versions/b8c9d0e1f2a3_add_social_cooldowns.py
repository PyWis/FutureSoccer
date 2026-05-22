"""add_social_cooldowns

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-20 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.add_column(sa.Column('social_cooldown_json', sa.Text(), nullable=True,
                                      server_default='{}'))
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.add_column(sa.Column('social_deactivated_json', sa.Text(), nullable=True,
                                      server_default='{}'))


def downgrade():
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.drop_column('social_deactivated_json')
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.drop_column('social_cooldown_json')
