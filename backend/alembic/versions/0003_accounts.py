"""User accounts and revocable bearer sessions. Revision: 0003_accounts"""
from alembic import op
import sqlalchemy as sa
revision = '0003_accounts'
down_revision = '0002_probe_leases'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('failed_logins', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table('login_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_login_sessions_user_id', 'login_sessions', ['user_id'])
    op.create_index('ix_login_sessions_token_hash', 'login_sessions', ['token_hash'], unique=True)

def downgrade():
    op.drop_index('ix_login_sessions_token_hash', table_name='login_sessions')
    op.drop_index('ix_login_sessions_user_id', table_name='login_sessions')
    op.drop_table('login_sessions')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
