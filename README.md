# Backend — Chaski Pe

> Estado: **FASE 8 — PostgreSQL** (SQLAlchemy + Alembic).
> Si la base de datos no responde, la API cae a persistencia **en memoria**
> y lo avisa en `/health`.

## Tecnologias

- **Python 3.11 / 3.12**
- **FastAPI** + **Uvicorn**
- **Pydantic v2**
- **SQLAlchemy 2.0** + **Alembic** (migraciones)
- **PostgreSQL 16** (contenedor Docker)

## Arquitectura

```
React  →  FastAPI  →  PostgreSQL   (con fallback a memoria)
```

El frontend **no** se conecta a la base de datos. El backend usa un
**repositorio** (`app/services/repository.py`) con dos implementaciones:
`SqlRepository` (PostgreSQL) y `MemoryRepository` (fallback). `configure_repository()`
elige una al arrancar.

- **Sin autenticacion** todavia (un unico usuario, id=1).
- **Sin endpoint de inferencia**: el modelo corre en el navegador.

## Puesta en marcha

### 1. Base de datos (Docker)

```bash
# desde la raiz del repo
docker compose up -d db
```

### 2. Backend

```bash
cd backend
py -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate en Unix)
pip install -r requirements.txt
alembic upgrade head              # aplica el esquema
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000 · Docs: http://127.0.0.1:8000/docs
- `GET /health` -> `persistence` es `postgresql` o `memory`

Sin Docker/PostgreSQL el backend igual arranca (persistencia en memoria).

## Estructura

```
backend/
├── app/
│   ├── main.py             # FastAPI, CORS, /health, lifespan
│   ├── api/                # profile.py, history.py, phrases.py
│   ├── schemas/            # modelos Pydantic (entrada/salida)
│   ├── db/base.py          # modelos SQLAlchemy + engine
│   ├── services/
│   │   ├── repository.py   # MemoryRepository + SqlRepository + semilla
│   │   └── store.py        # seleccion del repositorio
│   └── core/config.py      # settings (env CHASKIPE_*)
├── alembic/                # migraciones
│   └── versions/
├── tests/                  # pytest
├── alembic.ini
└── requirements.txt
```

## Endpoints (`/api/v1`)

| Metodo | Ruta | Descripcion |
| ------ | ---- | ----------- |
| GET    | `/profile` | Perfil del usuario |
| PUT    | `/profile` | Actualiza nombre y correo |
| GET    | `/history` | Historial (`?limit=N`) |
| POST   | `/history` | Anade una entrada |
| DELETE | `/history/{id}` | Borra una entrada (404 si no existe) |
| DELETE | `/history` | Vacia el historial |
| GET    | `/phrases` | Frases rapidas por categoria |
| GET    | `/health` | Estado + tipo de persistencia (sin prefijo) |

## Configuracion (variables de entorno)

| Variable | Por defecto | |
| -------- | ----------- | --- |
| `CHASKIPE_DATABASE_URL` | `postgresql+psycopg://chaskipe:chaskipe@localhost:5432/chaskipe` | URL de la BD |
| `CHASKIPE_REQUIRE_DATABASE` | `false` | si `true`, el backend falla al arrancar sin BD |
| `CHASKIPE_ENVIRONMENT` | `development` | |

## Migraciones (Alembic)

```bash
alembic upgrade head                       # aplicar todas
alembic revision --autogenerate -m "..."   # crear una tras cambiar los modelos
alembic downgrade -1                        # revertir la ultima
alembic current                             # version aplicada
```

## Pruebas

```bash
cd backend
.venv\Scripts\activate
pytest -q
```

Los tests de la API corren contra el repositorio **en memoria** (rapido, sin BD).
`test_persistence.py` prueba la seleccion de repositorio y, si hay PostgreSQL
disponible, la integracion real (si no, se salta).

## Notas de datos

- Todo lo relacionado con senas LSP viaja con `is_demo: true` / `es_demo=true`:
  no esta validado con personas usuarias de LSP ni interpretes.
- Los datos semilla (perfil "Andersson", 3 entradas de historial, frases) se
  insertan solo si las tablas estan vacias.

## Pendiente

- [ ] Autenticacion / usuarios (varios perfiles).
- [ ] `preferencias_usuario`, catalogo de `senas`, `animaciones_sena`.
