"""Phase 3 baseline schema. Fresh installs only.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
from app.db import Base
from app import models  # noqa: F401
from sqlalchemy import MetaData

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Baseline from Phase 3; new fields are added in revision 0002.
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name in ('users', 'login_sessions'):
            continue
        clone = table.to_metadata(metadata)
        if clone.name == 'monitors':
            clone._columns.remove(clone.c.check_lease_token)
            clone._columns.remove(clone.c.check_lease_until)
    metadata.create_all(bind=op.get_bind(), checkfirst=False)

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
