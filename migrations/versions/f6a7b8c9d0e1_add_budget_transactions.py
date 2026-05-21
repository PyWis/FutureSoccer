"""add_budget_transactions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'budget_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('game_day', sa.Integer(), nullable=False),
        sa.Column('game_week_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('budget_transactions', schema=None) as batch_op:
        batch_op.create_index('ix_budget_transactions_team_id', ['team_id'])
        batch_op.create_index('ix_budget_transactions_game_week_id', ['game_week_id'])
        batch_op.create_index('ix_budget_transactions_season', ['season'])


def downgrade():
    with op.batch_alter_table('budget_transactions', schema=None) as batch_op:
        batch_op.drop_index('ix_budget_transactions_season')
        batch_op.drop_index('ix_budget_transactions_game_week_id')
        batch_op.drop_index('ix_budget_transactions_team_id')
    op.drop_table('budget_transactions')
