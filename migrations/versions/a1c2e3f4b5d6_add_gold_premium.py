"""add premium Gold currency, wallet, transactions and team gold features

Revision ID: a1c2e3f4b5d6
Revises: f7a8b9c0d1e2
Create Date: 2099-09-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1c2e3f4b5d6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gold', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('seasonal_pass_season', sa.Integer(), nullable=True, server_default='-1'))

    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gold_scouting_active', sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column('gold_scouting_last_month', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('gold_roster_slots', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('gold_roster_last_month', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('gold_sponsor_slots', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('gold_sponsor_last_month', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('xmas_pass_last_year', sa.Integer(), nullable=True, server_default='0'))

    with op.batch_alter_table('active_sponsors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=True, server_default=sa.false()))

    op.create_table(
        'gold_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_gold_transactions_user_id', 'gold_transactions', ['user_id'])


def downgrade():
    op.drop_index('ix_gold_transactions_user_id', table_name='gold_transactions')
    op.drop_table('gold_transactions')
    with op.batch_alter_table('active_sponsors', schema=None) as batch_op:
        batch_op.drop_column('locked')
    with op.batch_alter_table('teams', schema=None) as batch_op:
        for col in ('xmas_pass_last_year', 'gold_sponsor_last_month', 'gold_sponsor_slots',
                    'gold_roster_last_month', 'gold_roster_slots', 'gold_scouting_last_month',
                    'gold_scouting_active'):
            batch_op.drop_column(col)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('seasonal_pass_season')
        batch_op.drop_column('gold')
