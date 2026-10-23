from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.author import Author
from app.models.book import Book
from app.schemas.book import BookCreate, BookOut, BookUpdate
from app.services.books import count_books_by_author

router = APIRouter()


def _get_book_or_404(db: Session, book_id: int) -> Book:
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


def _require_author(db: Session, author_id: int) -> None:
    if db.query(Author).filter(Author.id == author_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")


@router.get("", response_model=List[BookOut])
@router.get("/", response_model=List[BookOut], include_in_schema=False)
def list_books(
    q: Optional[str] = Query(None, description="Case-insensitive title search"),
    limit: int = Query(50, ge=1, le=200),  # query parameters are validated and documented for free
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Book)
    if q:
        query = query.filter(Book.title.ilike(f"%{q}%"))
    return query.order_by(Book.title).offset(offset).limit(limit).all()


# Declared before "/{book_id}" so that "stats" isn't parsed as a book id: route order matters.
@router.get("/stats")
def books_per_author(db: Session = Depends(get_db)):
    return count_books_by_author(db)


@router.post("", response_model=BookOut, status_code=201)
@router.post("/", response_model=BookOut, status_code=201, include_in_schema=False)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    _require_author(db, payload.author_id)
    book = Book(title=payload.title, year=payload.year, author_id=payload.author_id)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return _get_book_or_404(db, book_id)


@router.patch("/{book_id}", response_model=BookOut)
def update_book(book_id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    book = _get_book_or_404(db, book_id)
    updates = payload.dict(exclude_unset=True)
    if "author_id" in updates:
        _require_author(db, updates["author_id"])
    for field, value in updates.items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    db.delete(_get_book_or_404(db, book_id))
    db.commit()
