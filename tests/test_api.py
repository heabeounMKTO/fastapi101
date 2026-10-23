import pytest


def make_author(client, name="Ursula K. Le Guin", **extra):
    r = client.post("/api/v1/authors", json={"name": name, **extra})
    assert r.status_code == 201
    return r.json()


def test_root_health(client):
    r = client.get("/api/v1")
    assert r.status_code == 200
    assert r.json()["status"] == "online"


def test_api_responses_are_never_cached(client):
    assert client.get("/api/v1").headers["cache-control"] == "no-store"


# ── authors ──────────────────────────────────────────────────────────────────


def test_create_and_get_author(client):
    author = make_author(client, country="USA")
    r = client.get(f"/api/v1/authors/{author['id']}")
    assert r.status_code == 200
    assert r.json()["country"] == "USA"


def test_duplicate_author_name_conflicts(client):
    make_author(client)
    r = client.post("/api/v1/authors", json={"name": "Ursula K. Le Guin"})
    assert r.status_code == 409


def test_unknown_author_is_404(client):
    assert client.get("/api/v1/authors/999").status_code == 404


def test_patch_only_changes_sent_fields(client):
    author = make_author(client, country="USA")
    r = client.patch(f"/api/v1/authors/{author['id']}", json={"name": "U. K. Le Guin"})
    assert r.json()["name"] == "U. K. Le Guin"
    assert r.json()["country"] == "USA"


def test_cannot_delete_author_with_books(client):
    author = make_author(client)
    client.post("/api/v1/books", json={"title": "A Wizard of Earthsea", "author_id": author["id"]})
    assert client.delete(f"/api/v1/authors/{author['id']}").status_code == 409


# ── books ────────────────────────────────────────────────────────────────────


def test_create_book_and_list_under_author(client):
    author = make_author(client)
    r = client.post("/api/v1/books", json={"title": "The Dispossessed", "year": 1974, "author_id": author["id"]})
    assert r.status_code == 201
    books = client.get(f"/api/v1/authors/{author['id']}/books").json()
    assert [b["title"] for b in books] == ["The Dispossessed"]


def test_book_needs_an_existing_author(client):
    r = client.post("/api/v1/books", json={"title": "Orphan", "author_id": 123})
    assert r.status_code == 404


@pytest.mark.parametrize("body", [{"title": "", "author_id": 1}, {"title": "x", "year": -5, "author_id": 1}, {"author_id": 1}])
def test_invalid_book_payload_is_422(client, body):
    assert client.post("/api/v1/books", json=body).status_code == 422


def test_search_and_paginate_books(client):
    author = make_author(client)
    for title in ["Alpha", "Beta", "Alphabet"]:
        client.post("/api/v1/books", json={"title": title, "author_id": author["id"]})
    assert [b["title"] for b in client.get("/api/v1/books?q=alpha").json()] == ["Alpha", "Alphabet"]
    assert len(client.get("/api/v1/books?limit=2").json()) == 2


def test_books_per_author_stats(client):
    busy, idle = make_author(client, "Busy"), make_author(client, "Idle")
    for title in ["One", "Two"]:
        client.post("/api/v1/books", json={"title": title, "author_id": busy["id"]})
    stats = client.get("/api/v1/books/stats").json()
    assert stats == [
        {"author_id": busy["id"], "author": "Busy", "books": 2},
        {"author_id": idle["id"], "author": "Idle", "books": 0},
    ]
