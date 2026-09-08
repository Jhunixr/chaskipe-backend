"""
Punto de entrada de la API de Chaski Pe (FASE 8).

    cd backend
    .venv\\Scripts\\activate
    uvicorn app.main:app --reload

Docs interactivas: http://127.0.0.1:8000/docs

Alcance FASE 8:
- Perfil, historial y frases rapidas.
- Persistencia en **PostgreSQL** (SQLAlchemy). Si la base de datos no responde,
  la API cae a persistencia EN MEMORIA y lo avisa en /health.
- Sin autenticacion. Sin endpoint de inferencia (el modelo corre en el navegador).

Base de datos:
    docker compose up -d db      (desde la raiz del repo)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, history, phrases, preferences, profile
from app.core.config import settings
from app.services import store


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.configure_repository()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="API de perfil, historial y frases rapidas de Chaski Pe.",
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
