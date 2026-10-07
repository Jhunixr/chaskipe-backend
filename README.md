# Backend — Chaski Pe

> FastAPI + SQLAlchemy + Alembic sobre **PostgreSQL 16 (Docker)**.
> Cuentas con JWT, historial, frases, vocabulario de senas LSP, reportes de
> reconocimiento y subida de muestras del dataset.
> En desarrollo, si la base de datos no responde, cae a memoria y lo avisa en
> `/health`; en produccion **no arranca** sin base de datos.

## Tecnologias

- **Python 3.11 / 3.12**
- **FastAPI** + **Uvicorn**, **Pydantic v2**
- **SQLAlchemy 2.0** + **Alembic** (migraciones), driver **psycopg 3**
- **PostgreSQL 16** (contenedor Docker)
- **bcrypt** (contrasenas) + **JWT** (sesiones)

## Arquitectura

```
React  →  FastAPI  →  PostgreSQL   (fallback a memoria solo en desarrollo)
                 ↘  disco: muestras del dataset (JSON, un archivo por grabacion)
```

El frontend **no** se conecta a la base de datos. El backend usa un
**repositorio** (`app/services/repository.py`) con dos implementaciones:
`SqlRepository` (PostgreSQL) y `MemoryRepository` (fallback). Los modelos de
reconocimiento corren en el navegador: **no hay endpoint de inferencia**.

## Puesta en marcha (desarrollo)

```bash
# 1. Base de datos (desde la raiz del repo)
docker compose up -d db

# 2. Backend
cd backend
py -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate en Unix)
pip install -r requirements.txt
alembic upgrade head              # aplica el esquema
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000 · Docs: http://127.0.0.1:8000/docs
- `GET /health` → `persistence` es `postgresql` o `memory`

## Despliegue en Dokploy (VPS)

La base de datos `chaskipe-db` de Dokploy **es un contenedor Docker** de
PostgreSQL. La API se despliega con el `Dockerfile` de esta carpeta: al
arrancar aplica las migraciones (`start.sh`) y luego levanta uvicorn como
usuario sin privilegios.

1. **Aplicacion** → Build type *Dockerfile*. Hoy se despliega desde el repo
   `Jhunixr/chaskipe-backend`, rama `backend-python`, Build Path `/`
   (copia de la carpeta `backend/` del monorepo `chaskipe`).
   **Autodeploy esta activo**: cada push a `backend-python` redespliega.
2. **Environment** (ver `.env.example`):

   ```env
   CHASKIPE_ENVIRONMENT=production
   CHASKIPE_DATABASE_URL=<Internal Connection URL de chaskipe-db>
   CHASKIPE_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
   CHASKIPE_CORS_ORIGINS=["https://<dominio-del-frontend>"]
   CHASKIPE_ADMIN_TOKEN=<otro secreto largo>
   ```

   La *Internal Connection URL* se pega **tal cual** (`postgresql://...`): el
   backend la convierte al driver psycopg 3. Antes esto fallaba en silencio y
   la API funcionaba en memoria, perdiendo los datos en cada reinicio.
3. **Volumes** → montar un volumen en `/app/data` (ahi se guardan las
   muestras subidas desde la app; sin volumen se pierden al redesplegar).
4. Desplegar y comprobar: `GET /health` debe decir
   `"persistence": "postgresql"` y `"environment": "production"`.

En produccion el arranque **falla con un mensaje claro** si falta
`CHASKIPE_SECRET_KEY` o si la base de datos no responde (antes caia a
memoria). Los logs muestran a que base se conecto, con la contrasena oculta.

## Estructura

```
backend/
├── app/
│   ├── main.py             # FastAPI, CORS, /health, lifespan, logging
│   ├── api/                # auth, profile, preferences, history, phrases,
│   │                       # signs, recognition, dataset
│   ├── schemas/            # modelos Pydantic (entrada/salida)
│   ├── db/base.py          # modelos SQLAlchemy + engine
│   ├── services/
│   │   ├── repository.py   # MemoryRepository + SqlRepository + semilla
│   │   ├── vocabulary.py   # vocabulario semilla (33 senas) + modelos conocidos
│   │   ├── dataset_store.py# muestras del dataset en disco + export zip
│   │   └── store.py        # seleccion del repositorio
│   └── core/               # config.py (env CHASKIPE_*), security.py
├── alembic/versions/       # migraciones
├── tests/                  # pytest
├── Dockerfile, start.sh    # despliegue
└── requirements.txt
```

## Endpoints (`/api/v1`)

| Metodo | Ruta | Auth | Descripcion |
| ------ | ---- | ---- | ----------- |
| POST   | `/auth/register` · `/auth/login` | — | Crear cuenta / iniciar sesion (JWT) |
| GET    | `/auth/me` | si | Usuario de la sesion |
| GET/PUT | `/profile` | si | Perfil |
| GET/PUT | `/preferences` | si | Preferencias de accesibilidad |
| GET/POST/DELETE | `/history` · `/history/{id}` | si | Historial de traducciones |
| GET    | `/phrases` | — | Frases rapidas por categoria |
| GET    | `/signs` · `/signs/{etiqueta}` | — | **Vocabulario LSP** (33: palabras, frases, abecedario) con `validated` |
| POST   | `/recognition/reports` | opcional | **"No era esa sena"**: aviso de reconocimiento equivocado |
| GET    | `/recognition/models` | — | Modelos de reconocimiento (version, exactitud) |
| POST   | `/dataset/samples` | si | **Subir una grabacion** (solo landmarks, con consentimiento) |
| GET    | `/dataset/summary` | — | Muestras por sena (que falta grabar) |
| GET    | `/dataset/export` | `X-Admin-Token` | Zip con todas las muestras → `ai/data/raw/` |
| GET    | `/health` | — | Estado + persistencia (sin prefijo) |

### Dataset desde el celular

1. En la app, con cuenta: `/dev/dataset` → elegir sena → consentimiento →
   grabar → **Enviar al servidor**.
2. El servidor valida la muestra (21 puntos por mano, etiqueta del
   vocabulario, consentimiento) y la guarda en `CHASKIPE_DATASET_DIR`; la
   tabla `muestras_sena` lleva el registro. `validated` siempre llega `false`.
3. Para entrenar:

   ```bash
   curl -H "X-Admin-Token: $CHASKIPE_ADMIN_TOKEN" https://<api>/api/v1/dataset/export -o dataset.zip
   unzip dataset.zip -d ai/data/raw/
   ```

## Configuracion (variables de entorno)

| Variable | Por defecto | |
| -------- | ----------- | --- |
| `CHASKIPE_ENVIRONMENT` | `development` | `production` activa las comprobaciones de arranque |
| `CHASKIPE_DATABASE_URL` | `postgresql+psycopg://chaskipe:chaskipe@localhost:5432/chaskipe` | acepta tambien `postgresql://` y `postgres://` |
| `CHASKIPE_REQUIRE_DATABASE` | `false` (`true` en produccion) | fallar al arrancar sin BD |
| `CHASKIPE_SECRET_KEY` | aleatoria en desarrollo | **obligatoria en produccion** (firma los JWT) |
| `CHASKIPE_CORS_ORIGINS` | localhost:5173/4173 | lista JSON con el dominio del frontend |
| `CHASKIPE_DATASET_DIR` | `data/dataset` (`/app/data/dataset` en Docker) | donde se guardan las muestras |
| `CHASKIPE_MAX_SAMPLE_BYTES` | `1500000` | tamano maximo de una muestra |
| `CHASKIPE_ADMIN_TOKEN` | vacio (export desactivado) | protege `GET /dataset/export` |

## Migraciones (Alembic)

```bash
alembic upgrade head                       # aplicar todas
alembic check                              # modelos y migraciones coinciden
alembic revision --autogenerate -m "..."   # crear una tras cambiar los modelos
alembic downgrade -1                        # revertir la ultima
```

Al arrancar, el backend tambien siembra lo que falte (sin tocar lo existente):
frases rapidas, las 33 senas del vocabulario y el modelo `letras-v1`.

## Pruebas

```bash
cd backend
pytest -q
```

Los tests de la API corren contra el repositorio **en memoria** (rapido, sin
BD). `test_persistence.py` prueba ademas la integracion real si hay PostgreSQL
(`docker compose up -d db`); si no, esos tests se saltan.

## Notas de datos

- Ninguna sena sale validada (`validated: false` / `validada=false`): solo una
  revision con personas usuarias de LSP o interpretes lo cambia.
- Las muestras del dataset son coordenadas de landmarks: **nunca video**.
