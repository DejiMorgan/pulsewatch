"""Add monitor claim recovery fields.

Revision ID: 0002_probe_leases
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_probe_leases'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('monitors', sa.Column('check_lease_token', sa.String(length=64), nullable=True))
    op.add_column('monitors', sa.Column('check_lease_until', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('monitors', 'check_lease_until')
    op.drop_column('monitors', 'check_lease_token')
