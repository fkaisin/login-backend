"""Create asset table

Revision ID: 77de86041b8d
Revises: 9aeb2eae8413
Create Date: 2025-06-26 13:17:59.591042

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '77de86041b8d'
down_revision: Union[str, None] = '9aeb2eae8413'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # ### commands auto generated by Alembic - please adjust! ###
  op.create_table(
    'assets',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('token_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('qty', sa.Float(), nullable=False),
    sa.Column('mean_buy', sa.Float(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(
      ['token_id'],
      ['tokens.cg_id'],
    ),
    sa.ForeignKeyConstraint(['user_id'], ['users.uid'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_id', 'user_id', name='unique_token_user'),
  )
  op.create_index(op.f('ix_assets_user_id'), 'assets', ['user_id'], unique=False)
  # ### end Alembic commands ###


def downgrade() -> None:
  """Downgrade schema."""
  # ### commands auto generated by Alembic - please adjust! ###
  op.drop_index(op.f('ix_assets_user_id'), table_name='assets')
  op.drop_table('assets')
  # ### end Alembic commands ###
