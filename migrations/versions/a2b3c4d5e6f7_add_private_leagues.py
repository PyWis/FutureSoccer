"""add_private_leagues

Revision ID: a2b3c4d5e6f7
Revises: b8c9d0e1f2a3
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a2b3c4d5e6f7'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'private_leagues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('capacity', sa.Integer(), default=4),
        sa.Column('loan_id', sa.Integer(), sa.ForeignKey('loans.id'), nullable=True),
        sa.Column('status', sa.String(length=20), default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'private_league_seasons',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('league_id', sa.Integer(), sa.ForeignKey('private_leagues.id'), nullable=False),
        sa.Column('season_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), default='forming'),
        sa.Column('num_teams', sa.Integer(), nullable=True),
        sa.Column('capacity_at_start', sa.Integer(), nullable=True),
        sa.Column('start_game_day', sa.Integer(), nullable=True),
        sa.Column('end_game_day', sa.Integer(), nullable=True),
        sa.Column('prestige_base', sa.Float(), default=0.0),
        sa.Column('prestige_coefficient', sa.Float(), default=1000000.0),
        sa.Column('prestige_random', sa.Float(), default=1.0),
        sa.Column('prestige', sa.Float(), default=0.0),
        sa.Column('sponsor_amount', sa.Float(), default=0.0),
        sa.Column('total_budget', sa.Float(), default=0.0),
        sa.Column('last_payout_week_id', sa.Integer(), default=0),
        sa.Column('tiebreak_seed', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'private_league_memberships',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('league_id', sa.Integer(), sa.ForeignKey('private_leagues.id'), nullable=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('private_league_seasons.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('status', sa.String(length=20), default='active'),
        sa.Column('entry_fee_paid', sa.Boolean(), default=False),
        sa.Column('permanence_fee_paid', sa.Boolean(), default=False),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('draws', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('goals_for', sa.Integer(), default=0),
        sa.Column('goals_against', sa.Integer(), default=0),
        sa.Column('points', sa.Integer(), default=0),
        sa.Column('tiebreak_random', sa.Integer(), default=0),
        sa.Column('final_position', sa.Integer(), nullable=True),
        sa.Column('force_snapshot', sa.Float(), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('season_id', 'team_id', name='uq_plm_season_team'),
    )

    op.create_table(
        'private_league_matches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('private_league_seasons.id'), nullable=False),
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
    op.drop_table('private_league_matches')
    op.drop_table('private_league_memberships')
    op.drop_table('private_league_seasons')
    op.drop_table('private_leagues')
