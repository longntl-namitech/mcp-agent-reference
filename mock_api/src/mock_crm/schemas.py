from typing import Literal

from pydantic import BaseModel

Stage = Literal["lead", "qualified", "proposal", "won", "lost"]


class ContactIn(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    company_id: int | None = None


class ContactPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_id: int | None = None


class CompanyIn(BaseModel):
    name: str
    industry: str | None = None
    website: str | None = None


class CompanyPatch(BaseModel):
    name: str | None = None
    industry: str | None = None
    website: str | None = None


class DealIn(BaseModel):
    title: str
    amount: float = 0
    stage: Stage = "lead"
    company_id: int | None = None
    contact_id: int | None = None


class DealPatch(BaseModel):
    title: str | None = None
    amount: float | None = None
    stage: Stage | None = None
    company_id: int | None = None
    contact_id: int | None = None


class TaskIn(BaseModel):
    title: str
    due_date: str | None = None
    done: bool = False
    contact_id: int | None = None
    company_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    due_date: str | None = None
    done: bool | None = None
    contact_id: int | None = None
    company_id: int | None = None


class NoteIn(BaseModel):
    body: str
    created_at: str | None = None
    contact_id: int | None = None
    company_id: int | None = None


class NotePatch(BaseModel):
    body: str | None = None
    created_at: str | None = None
    contact_id: int | None = None
    company_id: int | None = None


class StageIn(BaseModel):
    stage: Stage


class MergeIn(BaseModel):
    keep_id: int
    merge_id: int
