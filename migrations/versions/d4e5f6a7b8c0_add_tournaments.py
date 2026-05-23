"""add_july_tournaments

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b8
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season', sa.Integer(), nullable=False, index=True),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('status', sa.String(length=20), default='active'),
        sa.Column('bracket_size', sa.Integer(), default=0),
        sa.Column('start_game_day', sa.Integer(), nullable=True),
        sa.Column('days_between_rounds', sa.Integer(), default=7),
        sa.Column('winner_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('season', 'kind', name='uq_tournament_season_kind'),
    )

    op.create_table(
        'tournament_matches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tournament_id', sa.Integer(), sa.ForeignKey('tournaments.id'), nullable=False),
        sa.Column('round_index', sa.Integer(), nullable=False),
        sa.Column('slot_index', sa.Integer(), nullable=False),
        sa.Column('home_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('away_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('scheduled_game_day', sa.Integer(), nullable=False, index=True),
        sa.Column('status', sa.String(length=20), default='scheduled'),
        sa.Column('home_score', sa.Integer(), nullable=True),
        sa.Column('away_score', sa.Integer(), nullable=True),
        sa.Column('decided_by_penalties', sa.Boolean(), default=False),
        sa.Column('winner_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('home_lineup_json', sa.Text(), default='{}'),
        sa.Column('away_lineup_json', sa.Text(), default='{}'),
        sa.Column('turns_json', sa.Text(), default='[]'),
        sa.Column('injuries_json', sa.Text(), default='[]'),
        sa.Column('played_game_day', sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_table('tournament_matches')
    op.drop_table('tournaments')
