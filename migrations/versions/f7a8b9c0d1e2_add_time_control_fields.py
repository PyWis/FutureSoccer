"""add time control fields to game_config

Revision ID: f7a8b9c0d1e2
Revises: d4e5f6a7b8c0
Create Date: 2099-08-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'd4e5f6a7b8c0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('game_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('time_mode', sa.String(length=10),
                                      nullable=False, server_default='default'))
        batch_op.add_column(sa.Column('week_transition_hour', sa.Integer(),
                                      nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('week_anchor_real', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('week_anchor_day', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('freeze_aug15', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('freeze_target', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fast_august', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('game_config', schema=None) as batch_op:
        batch_op.drop_column('fast_august')
        batch_op.drop_column('freeze_target')
        batch_op.drop_column('freeze_aug15')
        batch_op.drop_column('week_anchor_day')
        batch_op.drop_column('week_anchor_real')
        batch_op.drop_column('week_transition_hour')
        batch_op.drop_column('time_mode')
