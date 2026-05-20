"""add Hall of Fame fields and annual event tracking

Revision ID: b1c2d3e4f5a6
Revises: a9b3c4d5e6f7
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'b1c2d3e4f5a6'
down_revision = 'a9b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    team_cols = [c['name'] for c in inspector.get_columns('teams')]
    if 'last_age_year' not in team_cols:
        op.add_column('teams', sa.Column('last_age_year', sa.Integer(), nullable=True, server_default='0'))
    if 'last_retire_year' not in team_cols:
        op.add_column('teams', sa.Column('last_retire_year', sa.Integer(), nullable=True, server_default='0'))

    player_cols = [c['name'] for c in inspector.get_columns('players')]
    if 'is_hof' not in player_cols:
        op.add_column('players', sa.Column('is_hof', sa.Boolean(), nullable=True, server_default='0'))
    if 'hof_team_id' not in player_cols:
        op.add_column('players', sa.Column('hof_team_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('teams', 'last_age_year')
    op.drop_column('teams', 'last_retire_year')
    op.drop_column('players', 'is_hof')
    op.drop_column('players', 'hof_team_id')
