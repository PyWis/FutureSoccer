"""add_away_pending_subs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-20 15:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('friendly_matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('away_pending_subs_json', sa.Text(), nullable=True,
                                      server_default='{}'))


def downgrade():
    with op.batch_alter_table('friendly_matches', schema=None) as batch_op:
        batch_op.drop_column('away_pending_subs_json')
