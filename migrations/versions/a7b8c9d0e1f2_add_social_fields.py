"""add_social_fields

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-20 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.add_column(sa.Column('carisma', sa.Integer(), nullable=True, server_default='1'))
        batch_op.add_column(sa.Column('social_instok', sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column('social_sportsocial', sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column('social_fantasoccer', sa.Boolean(), nullable=True, server_default=sa.false()))

    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.add_column(sa.Column('social_effects_json', sa.Text(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('social_last_month_id', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('social_last_week_id', sa.Integer(), nullable=True, server_default='-1'))


def downgrade():
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.drop_column('social_last_week_id')
        batch_op.drop_column('social_last_month_id')
        batch_op.drop_column('social_effects_json')

    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.drop_column('social_fantasoccer')
        batch_op.drop_column('social_sportsocial')
        batch_op.drop_column('social_instok')
        batch_op.drop_column('carisma')
