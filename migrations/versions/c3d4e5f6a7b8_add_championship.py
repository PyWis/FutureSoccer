"""add_public_monthly_championship

Revision ID: c3d4e5f6a7b8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    # Team columns (server_default backfills existing rows).
    op.add_column('teams', sa.Column('is_bot', sa.Boolean(), nullable=True,
                                      server_default=sa.text('0')))
    op.add_column('teams', sa.Column('current_tier', sa.String(length=10), nullable=True,
                                      server_default='iron'))
    op.create_index('ix_teams_is_bot', 'teams', ['is_bot'])
    op.create_index('ix_teams_current_tier', 'teams', ['current_tier'])

    op.create_table(
        'championship_seasons',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('month_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('status', sa.String(length=20), default='forming'),
        sa.Column('start_game_day', sa.Integer(), nullable=True),
        sa.Column('last_matchday_game_day', sa.Integer(), nullable=True),
        sa.Column('end_game_day', sa.Integer(), nullable=True),
        sa.Column('tiebreak_seed', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'championship_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('championship_seasons.id'), nullable=False),
        sa.Column('tier', sa.String(length=10), nullable=False),
        sa.Column('group_index', sa.Integer(), nullable=False),
    )

    op.create_table(
        'championship_memberships',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('championship_seasons.id'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('championship_groups.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('draws', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('goals_for', sa.Integer(), default=0),
        sa.Column('goals_against', sa.Integer(), default=0),
        sa.Column('points', sa.Integer(), default=0),
        sa.Column('tiebreak_random', sa.Integer(), default=0),
        sa.Column('final_position', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('season_id', 'team_id', name='uq_cm_season_team'),
    )

    op.create_table(
        'championship_matches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('championship_seasons.id'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('championship_groups.id'), nullable=False),
        sa.Column('home_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('away_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('is_final_round', sa.Boolean(), default=False),
        sa.Column('scheduled_game_day', sa.Integer(), nullable=False, index=True),
        sa.Column('status', sa.String(length=20), default='scheduled'),
        sa.Column('home_score', sa.Integer(), nullable=True),
        sa.Column('away_score', sa.Integer(), nullable=True),
        sa.Column('home_lineup_json', sa.Text(), default='{}'),
        sa.Column('away_lineup_json', sa.Text(), default='{}'),
        sa.Column('turns_json', sa.Text(), default='[]'),
        sa.Column('injuries_json', sa.Text(), default='[]'),
        sa.Column('played_game_day', sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_table('championship_matches')
    op.drop_table('championship_memberships')
    op.drop_table('championship_groups')
    op.drop_table('championship_seasons')
    op.drop_index('ix_teams_current_tier', table_name='teams')
    op.drop_index('ix_teams_is_bot', table_name='teams')
    op.drop_column('teams', 'current_tier')
    op.drop_column('teams', 'is_bot')
