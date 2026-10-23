"""Shared fixtures. Tests run against an in-memory SQLite DB (the real DB is Postgres),
so they need no running services.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.database import Base, get_db


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()


@pytest.fixture
def client(engine):
    """A test client whose `get_db` dependency points at the in-memory DB."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    # dependency_overrides is how you swap any `Depends(...)` for a test double
    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
