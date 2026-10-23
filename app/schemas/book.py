from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1)  # validation happens before the route runs; bad input gets a 422
    year: Optional[int] = Field(None, ge=0, le=2100)
    author_id: int


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    year: Optional[int] = Field(None, ge=0, le=2100)
    author_id: Optional[int] = None


class BookOut(BaseModel):
    id: int
    title: str
    year: Optional[int] = None
    author_id: int
    created_at: datetime

    class Config:
        orm_mode = True
