# FastAPI 101

A tiny API (authors and books) laid out like our production services, with everything
business-specific stripped out. Read it top to bottom; every file is short.

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

Try the interactive docs at <http://localhost:8000/docs>. They are generated from the code above.

## Run it

```bash
cp .env.example .env      # set POSTGRES_HOST=localhost if running outside docker
make test                 # no database needed
make dev                  # starts Postgres in docker, migrates, runs the API with reload
# or everything in docker:
make up
```

## Exercises

1. Add a `genre` column to `Book`: edit the model and schemas, run `make migration m="add genre"`, look at the generated file, restart.
2. Add `GET /api/v1/books/{id}` with the author's name included in the response.
3. Write a test that fails first, then make it pass.
4. Protect `POST`/`DELETE` routes with a dependency (see `dependencies=[Depends(...)]` on `include_router`).

## Stack versions

FastAPI 0.103 with pydantic v1 (`orm_mode`, `.dict()`), SQLAlchemy 2.0, Alembic, Postgres 16, `uv` for dependencies.
Pydantic v2 renames a few things (`from_attributes`, `.model_dump()`), which is worth knowing when you read newer tutorials.
