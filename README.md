# FastAPI 101

A tiny API (authors and books). Read it top to bottom; every file is short.

New here? After getting it running, work through **[TUTORIAL.md](TUTORIAL.md)**: how the code works, then
building a feature end to end.

## Getting started

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.11 and the dependencies for you
- [Docker](https://docs.docker.com/get-docker/) with Compose, for Postgres (and for running everything in containers)
- `make`, which is optional: each target in the `Makefile` is a one-line command you can run yourself

### 1. Install dependencies

```bash
uv sync
```

This creates `.venv/` from `pyproject.toml` and `uv.lock`. Prefix commands with `uv run` (e.g. `uv run pytest`)
so they use that environment, or activate it with `source .venv/bin/activate`.

### 2. Run the tests

```bash
make test        # same as: uv run pytest
```

The tests use in-memory SQLite, so they need no database. If they pass, your setup works.

### 3. Configure the environment

```bash
cp .env.example .env
```

`.env` is git-ignored. What to put in it depends on where the API runs:

| You run the API... | `POSTGRES_HOST` | `POSTGRES_PORT` |
|--------------------|-----------------|-----------------|
| on your machine (`make dev`) | `localhost` | `5433` |
| in docker (`make up`) | `db` | `5432` |

Compose publishes Postgres on host port **5433** (see `docker-compose.yml`) so it won't clash with a Postgres
you may already have on 5432. Inside the docker network the API reaches it as `db:5432`.

### 4. Run the API

**Option A: API on your machine, Postgres in docker** (best for development; the server reloads when you save a file)

```bash
make dev
```

This starts the `db` container, applies migrations with `alembic upgrade head`, and runs `main.py`.

**Option B: everything in docker**

```bash
make up          # build and start db + api in the background
docker compose logs -f api
make down        # stop (add -v to docker compose down to also wipe the database volume)
```

The container's `run.sh` waits for the database, runs migrations, then starts the API.

### 5. Try it

- Health check: <http://localhost:8000/api/v1>
- Interactive docs (Swagger UI): <http://localhost:8000/docs>, generated from the code
- ReDoc: <http://localhost:8000/redoc>

Or from the command line:

```bash
curl -X POST localhost:8000/api/v1/authors -H 'Content-Type: application/json' \
     -d '{"name": "Ursula K. Le Guin", "country": "USA"}'

curl -X POST localhost:8000/api/v1/books -H 'Content-Type: application/json' \
     -d '{"title": "The Dispossessed", "year": 1974, "author_id": 1}'

curl localhost:8000/api/v1/books/stats
```

## Endpoints

All routes live under `/api/v1`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET, POST | `/authors` | List authors, create one |
| GET, PATCH, DELETE | `/authors/{id}` | Read, partially update, delete (409 if the author still has books) |
| GET | `/authors/{id}/books` | Books by one author |
| GET, POST | `/books` | List (`?q=`, `?limit=`, `?offset=`), create |
| GET | `/books/stats` | Book count per author |
| GET, PATCH, DELETE | `/books/{id}` | Read, partially update, delete |

## Tour

Follow one request, `POST /api/v1/books`, through the code:

| Step | File | What to notice |
|------|------|----------------|
| 1. App entry | `main.py` | `FastAPI(...)`, lifespan, CORS, a middleware, `include_router` with prefix + tags |
| 2. Config | `app/config.py` | Settings from environment variables, cached with `lru_cache` |
| 3. Database | `app/database.py` | Engine, `SessionLocal`, and `get_db`, the dependency that gives each request a session |
| 4. Validation | `app/schemas/book.py` | pydantic schemas: `Create` / `Update` / `Out`, `Field` constraints, `orm_mode` |
| 5. Route | `app/routes/books.py` | `Depends`, `response_model`, status codes, `HTTPException`, query params, route ordering |
| 6. Model | `app/models/book.py` | SQLAlchemy table, foreign key, `relationship` |
| 7. Service | `app/services/books.py` | Logic that isn't HTTP: a grouped query |
| 8. Migration | `alembic/versions/` | Schema changes as code. `run.sh` applies them on startup |
| 9. Tests | `tests/` | In-memory SQLite and `dependency_overrides` to swap out `get_db` |
| 10. Ship it | `Dockerfile`, `docker-compose.yml`, `run.sh` | Wait for DB, migrate, start |

## Project layout

```
main.py              app object, middleware, router registration
app/
  config.py          settings from env vars
  database.py        engine, session, get_db dependency
  models/            SQLAlchemy tables
  schemas/           pydantic request/response models
  routes/            one router per resource
  services/          logic that isn't tied to HTTP
alembic/versions/    database migrations
tests/               pytest suite (SQLite, no services needed)
```

## Common tasks

| Task | Command |
|------|---------|
| Run tests | `make test` |
| Run one test | `uv run pytest -k test_name` |
| Create a migration after changing a model | `make migration m="describe the change"`, then review the file in `alembic/versions/` |
| Apply migrations | `uv run alembic upgrade head` |
| Undo the last migration | `uv run alembic downgrade -1` |
| Add a dependency | `uv add <package>` (or `uv add --dev <package>`) |
| Open a Postgres shell | `docker compose exec db psql -U postgres` |

Autogenerate compares your models with the running database, so the database must be up (`make dev-db`) and
`.env` must point at it (see step 3).

## Exercises

1. Add a `genre` column to `Book`: edit the model and schemas, run `make migration m="add genre"`, look at the generated file, restart.
2. Add `GET /api/v1/books/{id}` with the author's name included in the response.
3. Write a test that fails first, then make it pass.
4. Protect `POST`/`DELETE` routes with a dependency (see `dependencies=[Depends(...)]` on `include_router`).

## Troubleshooting

- **`connection refused` on `make dev`**: check `.env` has `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433`, and that `docker compose ps` shows `db` as healthy.
- **`could not translate host name "db"`**: you're running outside docker with the docker settings. Use `localhost` / `5433`.
- **Port 8000 already in use**: change `API_PORT` (and `API_EXPOSE_PORT` for docker) in `.env`.
- **Start with a fresh database**: `docker compose down -v`, then `make dev` again.

## Stack versions

FastAPI 0.103 with pydantic v1 (`orm_mode`, `.dict()`), SQLAlchemy 2.0, Alembic, Postgres 16, `uv` for dependencies.
Pydantic v2 renames a few things (`from_attributes`, `.model_dump()`), which is worth knowing when you read newer tutorials.
