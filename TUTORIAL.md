# FastAPI 101: Tutorial

This tutorial has two parts:

1. **How it works.** Follow one request through the existing code and learn the main ideas: routers,
   dependencies, schemas, models, sessions, migrations and tests.
2. **Build a feature.** Add book **reviews** (rate a book 1 to 5, list reviews, get the average rating),
   touching every layer the way you would in a real service.

Before you start, get the project running with the [Getting started](README.md#getting-started) steps in the
README. You should be able to run `make test` and open <http://localhost:8000/docs>.

---

## Part 1: How it works

### The big picture

```
HTTP request
   │
   ▼
main.py            the FastAPI app: middleware, then picks a router by URL prefix
   │
   ▼
app/routes/*.py    the endpoint function: validates input, talks to the DB, returns data
   │  uses
   ├── app/schemas/*.py    pydantic: what the client may send and what it gets back
   ├── app/database.py     get_db: hands the route a database session
   ├── app/models/*.py     SQLAlchemy: Python classes mapped to tables
   └── app/services/*.py   logic that isn't about HTTP
   │
   ▼
JSON response
```

We'll follow `POST /api/v1/books` with this body:

```json
{"title": "The Dispossessed", "year": 1974, "author_id": 1}
```

### 1. The app and its routers (`main.py`)

```python
app = FastAPI(title="FastAPI 101", ..., lifespan=lifespan)

app.include_router(books.router, prefix="/api/v1/books", tags=["books"])
```

`FastAPI(...)` creates the application. Endpoints aren't declared here; they live in **routers**
(`APIRouter`), one per resource, and `include_router` mounts each one under a URL prefix. So a route declared
as `@router.post("")` in `app/routes/books.py` becomes `POST /api/v1/books`. `tags` groups the endpoints in
`/docs`.

Before the request reaches the router it passes through **middleware**. Middleware wraps every request,
so it's the place for cross-cutting behaviour. This project has two: `CORSMiddleware` (lets browsers on other
origins call the API) and `no_store_api_responses`, which adds a `Cache-Control` header to every response.

`lifespan` runs code once at startup (before `yield`) and once at shutdown (after it). Typical uses are
opening connection pools or loading a model into memory.

### 2. Configuration (`app/config.py`)

```python
class Settings(BaseModel):
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    ...

@lru_cache()
def get_settings():
    return Settings()
```

All configuration comes from environment variables, which `load_dotenv()` fills from `.env`. Nothing
environment-specific is hard-coded, so the same code runs on your laptop, in docker and in production.
`lru_cache` makes `get_settings()` build the object once and return the same one every time.

### 3. The endpoint (`app/routes/books.py`)

```python
@router.post("", response_model=BookOut, status_code=201)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    _require_author(db, payload.author_id)
    book = Book(title=payload.title, year=payload.year, author_id=payload.author_id)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book
```

FastAPI reads the function signature to decide what to do with the request:

| Parameter | Where FastAPI gets it |
|-----------|-----------------------|
| `payload: BookCreate` | A pydantic model, so it's parsed and validated from the **JSON body** |
| `db: Session = Depends(get_db)` | A **dependency**: FastAPI calls `get_db()` and passes in what it yields |
| `book_id: int` (in `get_book`) | Its name matches `{book_id}` in the path, so it's a **path parameter** |
| `q: Optional[str] = Query(None)` (in `list_books`) | Anything else simple is a **query parameter** (`?q=...`) |

The decorator controls the response:

- `response_model=BookOut` filters and validates what you return. You return a SQLAlchemy `Book`, and the
  client receives exactly the fields declared in `BookOut`, nothing more.
- `status_code=201` is the success code. `201 Created` is the convention for `POST`.

When something is wrong, **raise** `HTTPException(status_code=404, detail="...")`. FastAPI turns it into a
JSON error response. Helpers such as `_get_book_or_404` keep that check in one place.

> **Route order matters.** In `books.py`, `/stats` is declared before `/{book_id}`. Routes are matched top to
> bottom, so if `/{book_id}` came first, `GET /books/stats` would try to parse `"stats"` as an integer and
> return a 422.

### 4. Validation (`app/schemas/book.py`)

```python
class BookCreate(BaseModel):
    title: str = Field(..., min_length=1)
    year: Optional[int] = Field(None, ge=0, le=2100)
    author_id: int
```

Schemas are the API's contract. Each resource usually has three:

- `XCreate`: what a client sends to create one. Required fields have no default (or `...`).
- `XUpdate`: what a client sends to `PATCH`. Every field is optional.
- `XOut`: what the API returns. `orm_mode = True` lets pydantic read attributes from a SQLAlchemy object.

Validation happens **before your function runs**. Send `{"title": "", "author_id": 1}` and you get a `422`
listing exactly which field failed and why; `create_book` is never called.

**Why not return the model directly?** Schemas decouple the API from the database. You can add a column (say,
an internal flag) without leaking it to clients, and you can rename things on one side without breaking the
other.

### 5. Dependencies and sessions (`app/database.py`)

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`Depends(get_db)` means: before calling the route, run `get_db` until its `yield`, pass the session in, and
after the response is sent, run the `finally` block. Every request gets its own session, and it's always
closed, even if the route raises.

Dependencies are FastAPI's main tool for reuse. Anything a route needs (a DB session, the current user, a
permission check) can be a dependency, and in tests you can swap any of them out (see step 9).

The session is your unit of work with the database:

| Call | What it does |
|------|--------------|
| `db.query(Book).filter(...).first()` | `SELECT ... LIMIT 1`; returns a `Book` or `None` |
| `db.add(book)` | Stages a new row; nothing is sent yet |
| `db.commit()` | Writes everything staged in a transaction |
| `db.refresh(book)` | Re-reads the row so you get DB-generated values (`id`, `created_at`) |
| `db.delete(book)` | Stages a delete; `commit()` performs it |

### 6. Models (`app/models/book.py`)

```python
class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    author = relationship("Author", back_populates="books")
```

A model maps a Python class to a table. `ForeignKey` is the database-level link; `relationship` is the
Python-level one, so `book.author` gives the `Author` and `author.books` gives a list of books.
`back_populates` names the attribute on the other side; both sides must agree.

Every model must be imported in `app/models/__init__.py`. That import registers the table on `Base.metadata`,
which Alembic and the tests rely on to know the table exists.

### 7. Services (`app/services/books.py`)

`count_books_by_author` is a grouped query that powers `GET /books/stats`. It lives in a service because it
has nothing to do with HTTP: it takes a session and returns plain data. That makes it reusable (from another
route, a script, a background job) and easy to test. Rule of thumb: **routes translate HTTP to calls and
back; services hold the logic.**

### 8. Migrations (`alembic/versions/`)

Models describe the tables you want. Migrations are the steps that change a real database to match. Each
file has an `upgrade()` and a `downgrade()`, and a `down_revision` pointing to the previous file, which forms
a chain. `alembic upgrade head` applies every migration the database hasn't seen yet; `run.sh` does this
every time the container starts.

You rarely write migrations by hand: `make migration m="..."` compares your models with the database and
generates one. You always **read the generated file** before applying it, because autogenerate can miss
things (renames look like a drop plus an add, for example).

### 9. Tests (`tests/`)

```python
main.app.dependency_overrides[get_db] = override_get_db
with TestClient(main.app) as c:
    yield c
```

`conftest.py` builds a fresh in-memory SQLite database for each test, then uses `dependency_overrides` to make
every `Depends(get_db)` hand out sessions on that database instead of Postgres. `TestClient` sends real HTTP
requests to the app without starting a server. The result is fast, isolated tests that need no services.

### 10. Shipping it (`Dockerfile`, `docker-compose.yml`, `run.sh`)

The `Dockerfile` installs dependencies first and copies the code afterwards, so the slow dependency layer is
cached until `pyproject.toml` or `uv.lock` change. Compose starts Postgres, waits for its healthcheck, then
starts the API, whose `run.sh` waits for the database port, migrates, and launches the app.

---

## Part 2: Build a feature: book reviews

You'll add a `reviews` resource:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/reviews` | Review a book (rating 1 to 5, optional comment) |
| GET | `/api/v1/reviews?book_id=` | List reviews, optionally for one book |
| GET | `/api/v1/reviews/average?book_id=` | Average rating of a book |
| DELETE | `/api/v1/reviews/{id}` | Delete a review |

And one rule: **deleting a book deletes its reviews.**

Work on a branch so you can throw it away afterwards:

```bash
git switch -c tutorial-reviews
```

### Step 1: The model

Create `app/models/review.py`:

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Review(Base):
    """A reader's rating of one book."""

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    book = relationship("Book", back_populates="reviews")
```

Register it in `app/models/__init__.py`:

```python
from app.models.review import Review  # noqa: F401
```

Add the other side of the relationship to `Book` in `app/models/book.py`:

```python
    author = relationship("Author", back_populates="books")
    reviews = relationship("Review", back_populates="book", cascade="all, delete-orphan")
```

`cascade="all, delete-orphan"` means that when SQLAlchemy deletes a `Book`, it deletes the book's reviews too.
Without it, deleting a reviewed book would fail: SQLAlchemy would try to set the reviews' `book_id` to `NULL`,
which the column doesn't allow, and the request would end in a 500.

> Compare with authors: `DELETE /authors/{id}` refuses (409) when the author still has books. Cascading and
> refusing are both valid. Pick per relationship based on whether the children make sense on their own.

### Step 2: The migration

Make sure the database is running and `.env` points at it (`localhost` / `5433`, see the README), then:

```bash
make migration m="create reviews"
```

Open the new file in `alembic/versions/`. Its `upgrade()` should create a `reviews` table with the five
columns, a foreign key to `books.id`, and indexes on `id` and `book_id`, roughly:

```python
def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reviews_book_id"), "reviews", ["book_id"], unique=False)
    op.create_index(op.f("ix_reviews_id"), "reviews", ["id"], unique=False)
```

`downgrade()` should drop the indexes and the table. If the file is empty (`pass`), the model isn't
registered in `app/models/__init__.py`, or `.env` points at the wrong database.

Apply it and check you can go back and forth:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

You can look at the result with `docker compose exec db psql -U postgres -c '\d reviews'`.

### Step 3: The schemas

Create `app/schemas/review.py`:

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    book_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ReviewOut(BaseModel):
    id: int
    book_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
```

The `1 <= rating <= 5` rule lives in the schema, so the route never sees a bad rating. There's no
`ReviewUpdate` because this feature doesn't allow editing reviews; adding it is an exercise below.

### Step 4: The service

Create `app/services/reviews.py`:

```python
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.review import Review


def average_rating(db: Session, book_id: int) -> Optional[float]:
    """Mean rating of one book, or None if nobody has reviewed it yet."""
    avg = db.query(func.avg(Review.rating)).filter(Review.book_id == book_id).scalar()
    return round(float(avg), 2) if avg is not None else None
```

`func.avg` runs `AVG(rating)` in the database, so you don't load every review into Python to average them.
`.scalar()` returns the single value of a one-row, one-column result. Postgres returns a `Decimal`, hence
`float(...)`.

### Step 5: The routes

Create `app/routes/reviews.py`:

```python
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.book import Book
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewOut
from app.services.reviews import average_rating

router = APIRouter()


def _require_book(db: Session, book_id: int) -> None:
    if db.query(Book).filter(Book.id == book_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")


@router.get("", response_model=List[ReviewOut])
@router.get("/", response_model=List[ReviewOut], include_in_schema=False)
def list_reviews(
    book_id: Optional[int] = Query(None, description="Only reviews of this book"),
    db: Session = Depends(get_db),
):
    query = db.query(Review)
    if book_id is not None:
        query = query.filter(Review.book_id == book_id)
    return query.order_by(Review.created_at.desc(), Review.id.desc()).all()


@router.get("/average")
def get_average_rating(book_id: int, db: Session = Depends(get_db)):
    _require_book(db, book_id)
    return {"book_id": book_id, "average": average_rating(db, book_id)}


@router.post("", response_model=ReviewOut, status_code=201)
@router.post("/", response_model=ReviewOut, status_code=201, include_in_schema=False)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    _require_book(db, payload.book_id)
    review = Review(**payload.dict())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    db.delete(review)
    db.commit()
```

Things to notice:

- `get_average_rating` takes `book_id: int` with no `Query(...)` and no default, so it's a **required** query
  parameter. Call `/reviews/average` without it and you get a 422.
- `create_review` checks the book exists *before* inserting. The foreign key would also reject a bad
  `book_id`, but as a database error (a 500). Checking first gives the client a clear 404.
- `Review(**payload.dict())` works because the schema's field names match the model's columns.
- The pair of decorators (`""` and `"/"`) accepts the URL with and without a trailing slash, the same as the
  other routers.

### Step 6: Mount the router

In `main.py`, import the module and include it next to the others:

```python
from app.routes import root, authors, books, reviews
```

```python
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["reviews"])
```

### Step 7: Try it

```bash
make dev
```

Open <http://localhost:8000/docs>: there's a new **reviews** section. Or use curl:

```bash
curl -X POST localhost:8000/api/v1/authors -H 'Content-Type: application/json' \
     -d '{"name": "Octavia E. Butler"}'
curl -X POST localhost:8000/api/v1/books -H 'Content-Type: application/json' \
     -d '{"title": "Kindred", "author_id": 1}'

curl -X POST localhost:8000/api/v1/reviews -H 'Content-Type: application/json' \
     -d '{"book_id": 1, "rating": 5, "comment": "Unputdownable"}'
curl 'localhost:8000/api/v1/reviews/average?book_id=1'
# {"book_id":1,"average":5.0}

curl -X POST localhost:8000/api/v1/reviews -H 'Content-Type: application/json' \
     -d '{"book_id": 1, "rating": 9}'
# 422: "ensure this value is less than or equal to 5"
```

(Use whatever ids the `POST` calls actually returned if your database already had data.)

### Step 8: Tests

Create `tests/test_reviews.py`:

```python
import pytest


@pytest.fixture
def book(client):
    author = client.post("/api/v1/authors", json={"name": "Octavia E. Butler"}).json()
    return client.post("/api/v1/books", json={"title": "Kindred", "author_id": author["id"]}).json()


def test_create_and_list_reviews(client, book):
    r = client.post("/api/v1/reviews", json={"book_id": book["id"], "rating": 5, "comment": "Wow"})
    assert r.status_code == 201
    reviews = client.get(f"/api/v1/reviews?book_id={book['id']}").json()
    assert [rv["rating"] for rv in reviews] == [5]


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_1_to_5(client, book, rating):
    r = client.post("/api/v1/reviews", json={"book_id": book["id"], "rating": rating})
    assert r.status_code == 422


def test_review_needs_an_existing_book(client):
    assert client.post("/api/v1/reviews", json={"book_id": 999, "rating": 3}).status_code == 404


def test_average_rating(client, book):
    assert client.get(f"/api/v1/reviews/average?book_id={book['id']}").json()["average"] is None
    for rating in [4, 5]:
        client.post("/api/v1/reviews", json={"book_id": book["id"], "rating": rating})
    assert client.get(f"/api/v1/reviews/average?book_id={book['id']}").json()["average"] == 4.5


def test_deleting_a_book_deletes_its_reviews(client, book):
    client.post("/api/v1/reviews", json={"book_id": book["id"], "rating": 3})
    assert client.delete(f"/api/v1/books/{book['id']}").status_code == 204
    assert client.get("/api/v1/reviews").json() == []
```

The `book` fixture builds on the `client` fixture from `conftest.py`. Any test that asks for `book` gets a
fresh database that already contains one author and one book.

```bash
make test
```

All tests should pass, old and new. To see a test do its job, remove `cascade="all, delete-orphan"` from
`Book.reviews`, run `uv run pytest -k deleting_a_book`, and watch it fail. Then put the cascade back.

### Recap: adding any resource

| # | File | What |
|---|------|------|
| 1 | `app/models/<thing>.py` | The table, plus `relationship` on both sides |
| 2 | `app/models/__init__.py` | Import the model |
| 3 | `alembic/versions/` | `make migration m="..."`, read it, `alembic upgrade head` |
| 4 | `app/schemas/<thing>.py` | `Create` / `Update` / `Out` |
| 5 | `app/services/<thing>.py` | Any logic beyond simple CRUD |
| 6 | `app/routes/<thing>.py` | The endpoints |
| 7 | `main.py` | `include_router` with prefix and tag |
| 8 | `tests/test_<thing>.py` | Happy path, validation (422), missing parents (404), conflicts (409) |

---

## Exercises

1. **Edit a review.** Add `ReviewUpdate` and `PATCH /reviews/{id}`. Use `payload.dict(exclude_unset=True)`
   like `update_book` does, so a client can change just the comment.
2. **Average in the book.** Add `average_rating: Optional[float]` to a new `BookWithRatingOut` schema and return
   it from `GET /books/{id}`. Reuse the service.
3. **Top rated.** Add `GET /reviews/top?limit=5`: books ordered by average rating, best first. Write it as a
   service with a grouped query (see `count_books_by_author`) and test it. Where must the route be declared
   relative to `/{review_id}` routes, and why?
4. **One review per reader.** Add a `reviewer` column and a unique constraint on `(book_id, reviewer)`. Return
   a 409 on duplicates. You'll need a migration; check what autogenerate produces for the constraint.
5. **Protect writes.** Write a dependency that checks an `X-API-Key` header against a value in `Settings` and
   raises a 401 otherwise. Apply it to `POST` and `DELETE` only. In tests, use `dependency_overrides` to bypass
   it.

## Where to go next

- The official [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) covers each topic above in depth.
- This project uses pydantic v1. In v2, `orm_mode = True` becomes `model_config = ConfigDict(from_attributes=True)`
  and `.dict()` becomes `.model_dump()`. Expect to see the v2 names in newer docs.
- SQLAlchemy 2.0 also has a newer typed style (`Mapped[int]`, `mapped_column`, `select(...)`). The
  `db.query(...)` style used here still works and is common in existing code.
