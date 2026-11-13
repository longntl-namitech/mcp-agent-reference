import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from mock_crm.app import create_app
from mock_crm.db import reset_db

ALICE = {"Authorization": "Bearer demo-token-alice"}
STAGES = {"lead", "qualified", "proposal", "won", "lost"}


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "crm.db")


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path), headers=ALICE)


def count(client, entity):
    return len(client.get(f"/{entity}", params={"limit": 200}).json())


def test_requires_token(db_path):
    anon = TestClient(create_app(db_path))
    assert anon.get("/contacts").status_code == 401
    assert anon.get("/contacts", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert anon.get("/health").status_code == 200


def test_seed_counts(client):
    assert count(client, "companies") >= 8
    assert count(client, "contacts") >= 20
    deals = client.get("/deals", params={"limit": 200}).json()
    assert len(deals) >= 15
    assert {d["stage"] for d in deals} == STAGES


def test_crud_roundtrip_contact(client):
    body = {"name": "Test Person", "email": "t@example.com", "phone": "555-0100"}
    created = client.post("/contacts", json=body)
    assert created.status_code == 201
    cid = created.json()["id"]
    assert client.get(f"/contacts/{cid}").json()["name"] == "Test Person"
    patched = client.patch(f"/contacts/{cid}", json={"email": "new@example.com"})
    assert patched.json()["email"] == "new@example.com"
    assert patched.json()["name"] == "Test Person"
    assert client.delete(f"/contacts/{cid}").status_code == 204
    assert client.get(f"/contacts/{cid}").status_code == 404


def test_move_stage_validates(client):
    deal_id = client.get("/deals").json()[0]["id"]
    assert client.post(f"/deals/{deal_id}/stage", json={"stage": "closed"}).status_code == 422
    resp = client.post(f"/deals/{deal_id}/stage", json={"stage": "won"})
    assert resp.status_code == 200
    assert client.get(f"/deals/{deal_id}").json()["stage"] == "won"


def test_merge_contacts(client):
    keep = client.post("/contacts", json={"name": "Keep"}).json()["id"]
    merge = client.post("/contacts", json={"name": "Merge"}).json()["id"]
    note = client.post("/notes", json={"body": "hi", "contact_id": merge}).json()["id"]
    task = client.post("/tasks", json={"title": "t", "contact_id": merge}).json()["id"]
    deal = client.post("/deals", json={"title": "d", "contact_id": merge}).json()["id"]

    assert (
        client.post("/contacts/merge", json={"keep_id": keep, "merge_id": keep}).status_code == 409
    )
    assert (
        client.post("/contacts/merge", json={"keep_id": keep, "merge_id": 99999}).status_code == 404
    )
    assert (
        client.post("/contacts/merge", json={"keep_id": keep, "merge_id": merge}).status_code == 200
    )

    assert client.get(f"/notes/{note}").json()["contact_id"] == keep
    assert client.get(f"/tasks/{task}").json()["contact_id"] == keep
    assert client.get(f"/deals/{deal}").json()["contact_id"] == keep
    assert client.get(f"/contacts/{merge}").status_code == 404


def test_company_activities(client):
    company = client.get("/companies").json()[0]["id"]
    contact = client.post("/contacts", json={"name": "C", "company_id": company}).json()["id"]
    client.post("/notes", json={"body": "via contact", "contact_id": contact})
    client.post("/tasks", json={"title": "direct", "company_id": company})
    acts = client.get(f"/companies/{company}/activities")
    assert acts.status_code == 200
    bodies = [a.get("body") or a.get("title") for a in acts.json()]
    assert "via contact" in bodies and "direct" in bodies
    assert client.get("/companies/99999/activities").status_code == 404


def test_filters(client):
    won = client.get("/deals", params={"stage": "won"}).json()
    assert won and all(d["stage"] == "won" for d in won)


def test_reset_db(client, db_path):
    before = count(client, "contacts")
    first = client.get("/contacts").json()[0]["id"]
    client.delete(f"/contacts/{first}")
    assert count(client, "contacts") == before - 1
    reset_db(db_path)
    assert count(client, "contacts") == before


def test_limit_capped(client):
    assert client.get("/contacts", params={"limit": 1000}).status_code == 422
    assert len(client.get("/contacts", params={"limit": 2}).json()) == 2


def test_admin_reset_flag(db_path, monkeypatch):
    monkeypatch.delenv("MOCK_API_ALLOW_RESET", raising=False)
    off = TestClient(create_app(db_path), headers=ALICE)
    assert off.post("/admin/reset").status_code == 404

    monkeypatch.setenv("MOCK_API_ALLOW_RESET", "1")
    on = TestClient(create_app(db_path), headers=ALICE)
    before = count(on, "contacts")
    on.delete(f"/contacts/{on.get('/contacts').json()[0]['id']}")
    assert on.post("/admin/reset").status_code == 200
    assert count(on, "contacts") == before


async def test_concurrent_requests(db_path):
    app = create_app(db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t", headers=ALICE) as ac:
        results = await asyncio.gather(*[ac.get("/contacts") for _ in range(60)])
    assert [r.status_code for r in results] == [200] * 60


async def test_write_visible_immediately(db_path):
    app = create_app(db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t", headers=ALICE) as ac:
        for i in range(20):
            created = await ac.post("/contacts", json={"name": f"Fresh {i}"})
            got = await ac.get(f"/contacts/{created.json()['id']}")
            assert got.status_code == 200
