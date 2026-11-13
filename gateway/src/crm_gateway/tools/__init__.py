"""Tool sub-servers, one per CRM entity. Each exposes build_<entity>(api) -> FastMCP."""

from .companies import build_companies
from .contacts import build_contacts
from .deals import build_deals
from .notes import build_notes
from .reports import build_reports
from .tasks import build_tasks

WRITE_ACTIONS = ("create", "update", "delete", "move", "merge", "complete")

SUBSERVERS = {
    "contacts": build_contacts,
    "companies": build_companies,
    "deals": build_deals,
    "tasks": build_tasks,
    "notes": build_notes,
    "reports": build_reports,
}

__all__ = ["SUBSERVERS", "WRITE_ACTIONS", *(f.__name__ for f in SUBSERVERS.values())]
