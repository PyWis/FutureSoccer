"""add_loans

Revision ID: a1b2c3d4e5f6
Revises: 670afa43d25c
Create Date: 2026-05-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '670afa43d25c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('loans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('loan_type', sa.String(length=20), nullable=False),
        sa.Column('principal', sa.Float(), nullable=False),
        sa.Column('total_due', sa.Float(), nullable=False),
        sa.Column('weekly_payment', sa.Float(), nullable=False),
        sa.Column('weeks_total', sa.Integer(), nullable=False),
        sa.Column('weeks_paid', sa.Integer(), nullable=True),
        sa.Column('last_paid_week_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('loans')
