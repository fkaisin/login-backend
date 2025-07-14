"""Upgrading user table.

Revision ID: fdb90abc0094
Revises: 00f2f6f12466
Create Date: 2025-07-12 13:38:34.719566

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fdb90abc0094'
down_revision: Union[str, None] = '00f2f6f12466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    bind.execute(sa.text('DROP TABLE IF EXISTS _alembic_tmp_users'))

    with op.batch_alter_table('users') as batch_op:
        # Ajout des colonnes en une seule opération batch
        batch_op.add_column(sa.Column('fiat_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('calc_method_display', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('calc_method_tax', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('tax_principle', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Mise à jour des valeurs par défaut dans une étape séparée (hors batch)
    op.execute("UPDATE users SET fiat_id = 'fiat_eur' WHERE fiat_id IS NULL")
    op.execute("UPDATE users SET calc_method_display = 'weighted average' WHERE calc_method_display IS NULL")
    op.execute("UPDATE users SET calc_method_tax = 'fifo' WHERE calc_method_tax IS NULL")
    op.execute("UPDATE users SET tax_principle = 'pv' WHERE tax_principle IS NULL")

    # Maintenant modification des colonnes pour les passer en NOT NULL + ajout FK
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('fiat_id', nullable=False)
        batch_op.alter_column('calc_method_display', nullable=False)
        batch_op.alter_column('calc_method_tax', nullable=False)

        batch_op.create_foreign_key(
            'fiat_id_foreign_key',
            'tokens',
            ['fiat_id'],
            ['cg_id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    bind.execute(sa.text('DROP TABLE IF EXISTS _alembic_tmp_users'))

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fiat_id_foreign_key', type_='foreignkey')
        batch_op.drop_column('calc_method_tax')
        batch_op.drop_column('calc_method_display')
        batch_op.drop_column('fiat_id')
        batch_op.drop_column('tax_principle')
