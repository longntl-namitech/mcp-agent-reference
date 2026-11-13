import os
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel

from . import schemas as s
from .auth import require_user
from .db import get_conn, init_db, reset_db

# entity -> (create model, patch model, allowed query filters)
ENTITIES = {
    "contacts": (s.ContactIn, s.ContactPatch, ["company_id", "email", "name"]),
    "companies": (s.CompanyIn, s.CompanyPatch, ["industry", "name"]),
    "deals": (s.DealIn, s.DealPatch, ["stage", "company_id", "contact_id"]),
    "tasks": (s.TaskIn, s.TaskPatch, ["done", "contact_id", "company_id"]),
    "notes": (s.NoteIn, s.NotePatch, ["contact_id", "company_id"]),
}
LIKE_FILTERS = {"name"}
BOOL_FILTERS = {"done"}


def _row(row: sqlite3.Row, entity: str) -> dict:
    data = dict(row)
    if entity == "tasks":
        data["done"] = bool(data["done"])
    return data


def _get_or_404(conn: sqlite3.Connection, entity: str, item_id: int) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {entity} WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{entity[:-1]} {item_id} not found")
    return row


def _write(conn: sqlite3.Connection, sql: str, params: list) -> sqlite3.Cursor:
    try:
        return conn.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid reference: {exc}") from exc


def _values(model: BaseModel, entity: str) -> dict:
    data = model.model_dump(exclude_unset=True)
    if "done" in data:
        data["done"] = int(data["done"])
    return data


def _crud_router(entity, create_model, patch_model, filters, conn_dep) -> APIRouter:
    router = APIRouter(prefix=f"/{entity}", tags=[entity])

    @router.get("")
    def list_items(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        conn: sqlite3.Connection = Depends(conn_dep),
    ):
        where, params = [], []
        for name in filters:
            value = request.query_params.get(name)
            if value is None:
                continue
            if name in LIKE_FILTERS:
                where.append(f"{name} LIKE ?")
                params.append(f"%{value}%")
            elif name in BOOL_FILTERS:
                where.append(f"{name} = ?")
                params.append(int(value.lower() in ("1", "true", "yes")))
            else:
                where.append(f"{name} = ?")
                params.append(value)
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        rows = conn.execute(
            f"SELECT * FROM {entity}{clause} ORDER BY id LIMIT ? OFFSET ?", [*params, limit, offset]
        ).fetchall()
        return [_row(r, entity) for r in rows]

    @router.get("/{item_id}")
    def get_item(item_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
        return _row(_get_or_404(conn, entity, item_id), entity)

    @router.post("", status_code=201)
    def create_item(body: create_model, conn: sqlite3.Connection = Depends(conn_dep)):  # type: ignore[valid-type]
        data = _values(body, entity)
        if entity == "notes" and data.get("created_at") is None:
            data["created_at"] = datetime.now().isoformat(timespec="seconds")
        cols = list(data)
        cur = _write(
            conn,
            f"INSERT INTO {entity} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [data[c] for c in cols],
        )
        return _row(_get_or_404(conn, entity, cur.lastrowid), entity)

    @router.patch("/{item_id}")
    def patch_item(
        item_id: int,
        body: patch_model,  # type: ignore[valid-type]
        conn: sqlite3.Connection = Depends(conn_dep),
    ):
        _get_or_404(conn, entity, item_id)
        data = body.model_dump(exclude_unset=True)
        if "done" in data and data["done"] is not None:
            data["done"] = int(data["done"])
        if data:
            sets = ",".join(f"{c} = ?" for c in data)
            _write(conn, f"UPDATE {entity} SET {sets} WHERE id = ?", [*data.values(), item_id])
        return _row(_get_or_404(conn, entity, item_id), entity)

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
        _get_or_404(conn, entity, item_id)
        conn.execute(f"DELETE FROM {entity} WHERE id = ?", (item_id,))
        return Response(status_code=204)

    return router


def create_app(db_path: str) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Mock CRM API")

    def conn_dep():
        yield from get_conn(db_path)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    authed = APIRouter(dependencies=[Depends(require_user)])

    # Domain routes are registered before the CRUD routers so "/contacts/merge" is explicit.
    @authed.post("/contacts/merge")
    def merge_contacts(body: s.MergeIn, conn: sqlite3.Connection = Depends(conn_dep)):
        if body.keep_id == body.merge_id:
            raise HTTPException(status_code=409, detail="Cannot merge a contact into itself")
        _get_or_404(conn, "contacts", body.keep_id)
        _get_or_404(conn, "contacts", body.merge_id)
        for table in ("notes", "tasks", "deals"):
            conn.execute(
                f"UPDATE {table} SET contact_id = ? WHERE contact_id = ?",
                (body.keep_id, body.merge_id),
            )
        conn.execute("DELETE FROM contacts WHERE id = ?", (body.merge_id,))
        return _row(_get_or_404(conn, "contacts", body.keep_id), "contacts")

    @authed.post("/deals/{deal_id}/stage")
    def move_stage(deal_id: int, body: s.StageIn, conn: sqlite3.Connection = Depends(conn_dep)):
        _get_or_404(conn, "deals", deal_id)
        conn.execute("UPDATE deals SET stage = ? WHERE id = ?", (body.stage, deal_id))
        return _row(_get_or_404(conn, "deals", deal_id), "deals")

    @authed.get("/companies/{company_id}/activities")
    def company_activities(company_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
        _get_or_404(conn, "companies", company_id)
        contact_ids = "SELECT id FROM contacts WHERE company_id = :c"
        notes = conn.execute(
            f"SELECT * FROM notes WHERE company_id = :c OR contact_id IN ({contact_ids})",
            {"c": company_id},
        ).fetchall()
        tasks = conn.execute(
            f"SELECT * FROM tasks WHERE company_id = :c OR contact_id IN ({contact_ids})",
            {"c": company_id},
        ).fetchall()
        items = [{"type": "note", **_row(r, "notes"), "date": r["created_at"]} for r in notes]
        items += [{"type": "task", **_row(r, "tasks"), "date": r["due_date"] or ""} for r in tasks]
        items.sort(key=lambda i: i["date"], reverse=True)
        return items

    for entity, (create_model, patch_model, filters) in ENTITIES.items():
        authed.include_router(_crud_router(entity, create_model, patch_model, filters, conn_dep))
    app.include_router(authed)

    if os.environ.get("MOCK_API_ALLOW_RESET") == "1":

        @app.post("/admin/reset", dependencies=[Depends(require_user)])
        def admin_reset():
            reset_db(db_path)
            return {"status": "reset"}

    return app
