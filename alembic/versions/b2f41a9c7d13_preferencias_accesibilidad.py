"""preferencias de accesibilidad

Revision ID: b2f41a9c7d13
Revises: cd7bca5eb889
Create Date: 2026-09-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f41a9c7d13'
down_revision: Union[str, Sequence[str], None] = 'cd7bca5eb889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'preferencias_accesibilidad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tema', sa.String(length=10), nullable=False),
        sa.Column('tamano_texto', sa.String(length=12), nullable=False),
        sa.Column('velocidad_voz', sa.String(length=10), nullable=False),
        sa.Column('velocidad_avatar', sa.String(length=10), nullable=False),
        sa.Column('subtitulos', sa.Boolean(), nullable=False),
        sa.Column('idioma', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('preferencias_accesibilidad')
