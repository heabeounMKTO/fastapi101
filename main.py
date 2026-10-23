import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.routes import root, authors, books
import app.models  # noqa: F401 — registers all models with SQLAlchemy

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code before `yield` runs at startup, code after it at shutdown.
    print("Starting up...")
    yield
    print("Shutting down...")


app = FastAPI(
    title="FastAPI 101",
    description="A small teaching API: authors and books",
    version=os.getenv("API_VERSION", "0.1.0"),
    docs_url="/docs",  # interactive Swagger UI, generated from the code
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_store_api_responses(request, call_next):
    """A middleware wraps every request: here it tells browsers never to cache API responses."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# Each router is a group of related endpoints; the prefix and tags are set here, in one place.
app.include_router(root.router, prefix="/api/v1", tags=["root"])
app.include_router(authors.router, prefix="/api/v1/authors", tags=["authors"])
app.include_router(books.router, prefix="/api/v1/books", tags=["books"])

if __name__ == "__main__":
    if settings.env == "dev":
        uvicorn.run("main:app", reload=True, host="0.0.0.0", port=settings.app_port, log_level="debug")
    else:
        uvicorn.run("main:app", reload=False, host="0.0.0.0", port=settings.app_port, log_level="info")
