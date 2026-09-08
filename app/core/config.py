"""Configuracion del backend (FASE 7)."""
from __future__ import annotations

import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHASKIPE_", env_file=".env")

    app_name: str = "Chaski Pe API"
    version: str = "0.8.0"  # FASE 8
    environment: str = "development"

    # Origenes permitidos para CORS. Se usa una expresion regular porque Vite
    # cambia de puerto solo cuando el 5173 esta ocupado, y con una lista fija
    # el frontend se queda sin backend sin avisar.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",  # vite preview
    ]
    # Cualquier puerto de localhost/127.0.0.1 en desarrollo.
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1):\d+$"

    # Base de datos (FASE 8). Si esta vacia o no se puede conectar, la API
    # cae a persistencia EN MEMORIA y lo avisa en /health.
    database_url: str = (
        "postgresql+psycopg://chaskipe:chaskipe@localhost:5432/chaskipe"
    )
    # Si es True, el backend falla al arrancar si no hay base de datos.
    require_database: bool = False

    # --- Autenticacion ---
    # Clave para firmar los JWT. En desarrollo se genera una al azar en cada
    # arranque (los tokens dejan de valer al reiniciar, que es lo deseable).
    # En produccion DEBE definirse: CHASKIPE_SECRET_KEY=...
    secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7  # 7 dias


settings = Settings()
