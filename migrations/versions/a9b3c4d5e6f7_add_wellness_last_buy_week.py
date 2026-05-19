"""add wellness_last_buy_week_id to teams

Revision ID: a9b3c4d5e6f7
Revises: 8021a58ceef7
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'a9b3c4d5e6f7'
down_revision = '8021a58ceef7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('teams')]
    if 'wellness_last_buy_week_id' not in columns:
        op.add_column('teams', sa.Column('wellness_last_buy_week_id', sa.Integer(), nullable=True, server_default='-1'))


def downgrade():
    op.drop_column('teams', 'wellness_last_buy_week_id')
