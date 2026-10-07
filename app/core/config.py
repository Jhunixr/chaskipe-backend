"""Configuracion del backend (variables de entorno CHASKIPE_*)."""
from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prefijos de URL que dan Dokploy, Heroku, Railway, etc. SQLAlchemy los
# interpreta como psycopg2, que no esta instalado (usamos psycopg 3): sin
# normalizar, la conexion falla y la API cae a memoria sin que nadie lo note.
_PG_PREFIXES = ("postgres://", "postgresql://")
_PG_DRIVER = "postgresql+psycopg://"


def normalize_database_url(url: str) -> str:
    """`postgres://...` / `postgresql://...` -> `postgresql+psycopg://...`."""
    url = url.strip()
    for prefix in _PG_PREFIXES:
        if url.startswith(prefix):
            return _PG_DRIVER + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    # hide_input_in_errors: un error de validacion no debe imprimir la URL de
    # la base de datos (con su contrasena) en los logs del despliegue.
    model_config = SettingsConfigDict(
        env_prefix="CHASKIPE_", env_file=".env", hide_input_in_errors=True
    )

    app_name: str = "Chaski Pe API"
    version: str = "0.11.0"
    # "production" activa las comprobaciones de arranque (ver abajo).
    environment: str = "development"

    # Origenes permitidos para CORS. En produccion, el dominio del frontend:
    #   CHASKIPE_CORS_ORIGINS='["https://chaskipe.ejemplo.pe"]'
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",  # vite preview
    ]
    # Cualquier puerto de localhost/127.0.0.1 (http o https) en desarrollo:
    # Vite cambia de puerto cuando el 5173 esta ocupado y sirve por HTTPS.
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # Base de datos. Si esta vacia o no se puede conectar, la API cae a
    # persistencia EN MEMORIA y lo avisa en /health (salvo require_database).
    # Acepta la URL tal cual la da Dokploy (postgresql://...).
    database_url: str = (
        "postgresql+psycopg://chaskipe:chaskipe@localhost:5432/chaskipe"
    )
    # Si es True, el backend falla al arrancar si no hay base de datos.
    # En produccion es True salvo que se diga lo contrario.
    require_database: bool = False

    # --- Autenticacion ---
    # Clave para firmar los JWT. En desarrollo, si no se define, se genera una
    # al azar en cada arranque (los tokens dejan de valer al reiniciar).
    # En produccion es OBLIGATORIA: CHASKIPE_SECRET_KEY=...
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7  # 7 dias

    # --- Dataset de senas ---
    # Donde se guardan las muestras subidas desde la app (un JSON por
    # grabacion, mismo formato que ai/data/raw/). En Docker debe ser un
    # volumen persistente, si no se pierden al redesplegar.
    dataset_dir: Path = Path("data/dataset")
    # Tamano maximo de una muestra subida (bytes). ~2.5 s a 30 fps con dos
    # manos y world landmarks ocupa ~150 KB.
    max_sample_bytes: int = 1_500_000
    # Token para descargar el dataset completo (GET /dataset/export).
    # Vacio = la descarga esta desactivada.
    admin_token: str = ""

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        production = self.environment.strip().lower() == "production"
        if not self.secret_key:
            if production:
                raise ValueError(
                    "CHASKIPE_SECRET_KEY es obligatoria en produccion: sin ella "
                    "cada reinicio invalida todas las sesiones."
                )
            self.secret_key = secrets.token_urlsafe(32)
        if production and "require_database" not in self.model_fields_set:
            # En produccion caer a memoria es perder datos en silencio.
            self.require_database = True
        return self


settings = Settings()
