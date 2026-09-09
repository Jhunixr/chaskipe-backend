"""autenticacion y multiusuario

Anade contrasena a `usuarios` y liga `historial_traduccion` y
`preferencias_accesibilidad` a un usuario concreto.

Datos existentes: el proyecto asumia un unico usuario (id fijo = 1). Sus
filas se conservan y quedan asignadas a ese usuario, que pasa a tener una
contrasena no utilizable (hash invalido): para volver a entrar hay que
registrarse de nuevo o restablecerla. Asi no se inventa una contrasena
conocida que seria una puerta abierta.

Revision ID: c93e2f1a4b87
Revises: b2f41a9c7d13
Create Date: 2026-09-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c93e2f1a4b87'
down_revision: Union[str, Sequence[str], None] = 'b2f41a9c7d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Marcador que ningun hash bcrypt real puede igualar: verify() siempre falla.
UNUSABLE_PASSWORD = '!'


def upgrade() -> None:
    """Upgrade schema."""
    # --- usuarios: contrasena, fecha de alta, correo unico ---
    op.add_column(
        'usuarios',
        sa.Column(
            'contrasena_hash',
            sa.String(length=255),
            nullable=False,
            server_default=UNUSABLE_PASSWORD,
        ),
    )
    op.add_column(
        'usuarios',
        sa.Column(
            'creado_en',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )
    op.alter_column('usuarios', 'contrasena_hash', server_default=None)
    op.alter_column('usuarios', 'creado_en', server_default=None)
    op.create_index('ix_usuarios_correo', 'usuarios', ['correo'], unique=True)

    # --- garantizar que existe el usuario 1 antes de referenciarlo ---
    op.execute(
        sa.text(
            """
            INSERT INTO usuarios (id, nombre, correo, contrasena_hash, creado_en)
            SELECT 1, 'Usuario', 'usuario@chaskipe.local', :pwd, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE id = 1)
            """
        ).bindparams(pwd=UNUSABLE_PASSWORD)
    )

    # --- historial ligado al usuario ---
    op.add_column(
        'historial_traduccion',
        sa.Column('usuario_id', sa.Integer(), nullable=False, server_default='1'),
    )
    op.alter_column('historial_traduccion', 'usuario_id', server_default=None)
    op.create_index(
        'ix_historial_traduccion_usuario_id',
        'historial_traduccion',
        ['usuario_id'],
    )
    op.create_foreign_key(
        'fk_historial_usuario',
        'historial_traduccion',
        'usuarios',
        ['usuario_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # --- preferencias ligadas al usuario ---
    op.add_column(
        'preferencias_accesibilidad',
        sa.Column('usuario_id', sa.Integer(), nullable=False, server_default='1'),
    )
    op.alter_column(
        'preferencias_accesibilidad', 'usuario_id', server_default=None
    )
    op.create_index(
        'ix_preferencias_usuario_id',
        'preferencias_accesibilidad',
        ['usuario_id'],
        unique=True,
    )
    op.create_foreign_key(
        'fk_preferencias_usuario',
        'preferencias_accesibilidad',
        'usuarios',
        ['usuario_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # Avanzar las secuencias por encima de las filas ya existentes: si no, el
    # siguiente INSERT reutiliza un id ocupado y falla por clave duplicada.
    for table in ('usuarios', 'preferencias_accesibilidad'):
        op.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"GREATEST((SELECT COALESCE(MAX(id), 1) FROM {table}), 1))"
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_preferencias_usuario', 'preferencias_accesibilidad', type_='foreignkey'
    )
    op.drop_index('ix_preferencias_usuario_id', 'preferencias_accesibilidad')
    op.drop_column('preferencias_accesibilidad', 'usuario_id')

    op.drop_constraint(
        'fk_historial_usuario', 'historial_traduccion', type_='foreignkey'
    )
    op.drop_index('ix_historial_traduccion_usuario_id', 'historial_traduccion')
    op.drop_column('historial_traduccion', 'usuario_id')

    op.drop_index('ix_usuarios_correo', 'usuarios')
    op.drop_column('usuarios', 'creado_en')
    op.drop_column('usuarios', 'contrasena_hash')
