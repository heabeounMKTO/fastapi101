"""Services hold logic that doesn't belong in a route: reusable, and testable without HTTP."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.author import Author
from app.models.book import Book


def count_books_by_author(db: Session) -> list[dict]:
    """Authors with how many books each has, most prolific first."""
    rows = (
        db.query(Author.id, Author.name, func.count(Book.id))
        .outerjoin(Book, Book.author_id == Author.id)
        .group_by(Author.id, Author.name)
        .order_by(func.count(Book.id).desc(), Author.name)
        .all()
    )
    return [{"author_id": id_, "author": name, "books": count} for id_, name, count in rows]
