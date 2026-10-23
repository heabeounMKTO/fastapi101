# Importing every model here registers it on Base.metadata (needed by alembic and the tests).
from app.models.author import Author  # noqa: F401
from app.models.book import Book  # noqa: F401
