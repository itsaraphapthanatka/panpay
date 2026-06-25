"""topups and merchant wallet

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-24 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'merchants',
        sa.Column('balance', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
    )
    op.add_column(
        'merchants',
        sa.Column('credit_per_transaction', sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.create_table(
        'topups',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('merchant_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pay_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('trans_ref', sa.String(), nullable=True),
        sa.Column('promptpay_payload', sa.Text(), nullable=False),
        sa.Column('sender_name', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_topups_merchant_id'), 'topups', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_topups_pay_amount'), 'topups', ['pay_amount'], unique=False)
    op.create_index(op.f('ix_topups_status'), 'topups', ['status'], unique=False)
    op.create_index(op.f('ix_topups_trans_ref'), 'topups', ['trans_ref'], unique=True)
    op.create_index(op.f('ix_topups_created_at'), 'topups', ['created_at'], unique=False)
    op.create_table(
        'wallet_entries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('merchant_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('topup_id', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_wallet_entries_merchant_id'), 'wallet_entries', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_wallet_entries_created_at'), 'wallet_entries', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('wallet_entries')
    op.drop_index(op.f('ix_topups_created_at'), table_name='topups')
    op.drop_index(op.f('ix_topups_trans_ref'), table_name='topups')
    op.drop_index(op.f('ix_topups_status'), table_name='topups')
    op.drop_index(op.f('ix_topups_pay_amount'), table_name='topups')
    op.drop_index(op.f('ix_topups_merchant_id'), table_name='topups')
    op.drop_table('topups')
    op.drop_column('merchants', 'credit_per_transaction')
    op.drop_column('merchants', 'balance')
