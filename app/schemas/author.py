from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# Schemas are the API contract: what clients may send (Create/Update) and what they get back (Out).
class AuthorCreate(BaseModel):
    name: str
    country: Optional[str] = None


class AuthorUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None


class AuthorOut(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True  # lets pydantic read attributes straight off the SQLAlchemy object
