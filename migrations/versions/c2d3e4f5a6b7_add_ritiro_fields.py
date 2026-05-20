"""add ritiro estivo fields to teams

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    team_cols = [c['name'] for c in inspector.get_columns('teams')]

    if 'ritiro_year' not in team_cols:
        op.add_column('teams', sa.Column('ritiro_year', sa.Integer(), nullable=True, server_default='0'))
    if 'ritiro_type' not in team_cols:
        op.add_column('teams', sa.Column('ritiro_type', sa.String(20), nullable=True))
    if 'ritiro_end_day' not in team_cols:
        op.add_column('teams', sa.Column('ritiro_end_day', sa.Integer(), nullable=True, server_default='-1'))


def downgrade():
    op.drop_column('teams', 'ritiro_year')
    op.drop_column('teams', 'ritiro_type')
    op.drop_column('teams', 'ritiro_end_day')
