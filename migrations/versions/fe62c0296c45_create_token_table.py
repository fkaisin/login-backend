"""Create token table.

Revision ID: fe62c0296c45
Revises: d8f7f69ccc7d
Create Date: 2025-06-24 15:42:38.952023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'fe62c0296c45'
down_revision: Union[str, None] = 'd8f7f69ccc7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tokens',
    sa.Column('cg_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('mcap', sa.Integer(), nullable=True),
    sa.Column('image', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('change_1h', sa.Float(), nullable=False),
    sa.Column('change_24h', sa.Float(), nullable=False),
    sa.Column('change_7d', sa.Float(), nullable=False),
    sa.Column('change_30d', sa.Float(), nullable=False),
    sa.Column('change_1y', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('cg_id')
    )
    op.create_index(op.f('ix_tokens_symbol'), 'tokens', ['symbol'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_tokens_symbol'), table_name='tokens')
    op.drop_table('tokens')
    # ### end Alembic commands ###
