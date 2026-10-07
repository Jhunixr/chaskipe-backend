"""
Punto de entrada de la API de Chaski Pe.

    cd backend
    .venv\\Scripts\\activate
    uvicorn app.main:app --reload

Docs interactivas: http://127.0.0.1:8000/docs

Alcance:
- Cuentas (JWT), perfil, preferencias, historial y frases rapidas.
- Vocabulario de senas, reportes de reconocimiento, modelos y subida de
  muestras del dataset (solo landmarks).
- Persistencia en **PostgreSQL** (SQLAlchemy). Si la base de datos no responde,
  la API cae a persistencia EN MEMORIA y lo avisa en /health (en produccion,
  falla al arrancar).
- Sin endpoint de inferencia: los modelos corren en el navegador.

Base de datos:
    docker compose up -d db      (desde la raiz del repo)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, dataset, history, phrases, preferences, profile, recognition, signs
from app.core.config import settings
from app.services import store

# Uvicorn solo configura sus propios loggers: sin esto los avisos de la app
# (p. ej. por que no conecto la base de datos) no salen en los logs de Dokploy.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.configure_repository()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="API de Chaski Pe: cuentas, historial, frases, vocabulario LSP y dataset.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "persistence": store.current_backend(),
    }


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(profile.router, prefix=API_PREFIX)
app.include_router(preferences.router, prefix=API_PREFIX)
app.include_router(history.router, prefix=API_PREFIX)
app.include_router(phrases.router, prefix=API_PREFIX)
app.include_router(signs.router, prefix=API_PREFIX)
app.include_router(recognition.router, prefix=API_PREFIX)
app.include_router(dataset.router, prefix=API_PREFIX)
