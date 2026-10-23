from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.author import Author
from app.models.book import Book
from app.schemas.author import AuthorCreate, AuthorOut, AuthorUpdate
from app.schemas.book import BookOut

router = APIRouter()


def _get_author_or_404(db: Session, author_id: int) -> Author:
    author = db.query(Author).filter(Author.id == author_id).first()
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return author


@router.get("", response_model=List[AuthorOut])
@router.get("/", response_model=List[AuthorOut], include_in_schema=False)
def list_authors(db: Session = Depends(get_db)):
    return db.query(Author).order_by(Author.name).all()


@router.post("", response_model=AuthorOut, status_code=201)
@router.post("/", response_model=AuthorOut, status_code=201, include_in_schema=False)
def create_author(payload: AuthorCreate, db: Session = Depends(get_db)):
    if db.query(Author).filter(Author.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An author with this name already exists")
    author = Author(name=payload.name, country=payload.country)
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


@router.get("/{author_id}", response_model=AuthorOut)
def get_author(author_id: int, db: Session = Depends(get_db)):
    return _get_author_or_404(db, author_id)


@router.patch("/{author_id}", response_model=AuthorOut)
def update_author(author_id: int, payload: AuthorUpdate, db: Session = Depends(get_db)):
    author = _get_author_or_404(db, author_id)
    # exclude_unset: only touch the fields the client actually sent (that's what makes PATCH a PATCH)
    updates = payload.dict(exclude_unset=True)
    if "name" in updates:
        if db.query(Author).filter(Author.name == updates["name"], Author.id != author_id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An author with this name already exists")
    for field, value in updates.items():
        setattr(author, field, value)
    db.commit()
    db.refresh(author)
    return author


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int, db: Session = Depends(get_db)):
    author = _get_author_or_404(db, author_id)
    book_count = db.query(Book).filter(Book.author_id == author_id).count()
    if book_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete — this author has {book_count} book(s)",
        )
    db.delete(author)
    db.commit()


@router.get("/{author_id}/books", response_model=List[BookOut])
def get_author_books(author_id: int, db: Session = Depends(get_db)):
    """A nested resource: the books of one author."""
    _get_author_or_404(db, author_id)
    return db.query(Book).filter(Book.author_id == author_id).order_by(Book.title).all()
