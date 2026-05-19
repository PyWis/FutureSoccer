"""add_investments

Revision ID: add_investments_manual
Revises: ec375c314b9d
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_investments_manual'
down_revision = 'ec375c314b9d'
branch_labels = None
depends_on = None


def upgrade():
    # Table already created by db.create_all() — no-op if exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'investments' not in inspector.get_table_names():
        op.create_table(
            'investments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('team_id', sa.Integer(), nullable=False),
            sa.Column('bond_type', sa.String(length=20), nullable=False),
            sa.Column('original_type', sa.String(length=20), nullable=False),
            sa.Column('degraded', sa.Boolean(), nullable=True),
            sa.Column('cost', sa.Float(), nullable=False),
            sa.Column('payout', sa.Float(), nullable=False),
            sa.Column('weeks_total', sa.Integer(), nullable=False),
            sa.Column('game_week_id_bought', sa.Integer(), nullable=False),
            sa.Column('game_week_id_maturity', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    op.drop_table('investments')
