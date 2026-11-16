from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all


def build_tasks(api: ApiClient) -> FastMCP:
    mcp = FastMCP("tasks")

    @mcp.tool(name="list")
    async def list_tasks(limit: int = 50, offset: int = 0) -> dict | list:
        """List CRM tasks (follow-ups and to-dos), one page at a time, ordered by id."""
        return await call(api, "GET", "/tasks", params={"limit": limit, "offset": offset})

    @mcp.tool(name="get")
    async def get_task(id: int) -> dict | list:
        """Get one CRM task by id, with title, due date and done flag."""
        return await call(api, "GET", f"/tasks/{id}")

    @mcp.tool(name="create")
    async def create_task(
        title: str,
        due_date: str | None = None,
        contact_id: int | None = None,
        company_id: int | None = None,
    ) -> dict | list:
        """Create a new CRM task with a title and optional due date (YYYY-MM-DD)."""
        body = {
            "title": title,
            "due_date": due_date,
            "contact_id": contact_id,
            "company_id": company_id,
        }
        return await call(api, "POST", "/tasks", json=body)

    @mcp.tool(name="update")
    async def update_task(
        id: int,
        title: str | None = None,
        due_date: str | None = None,
        done: bool | None = None,
        contact_id: int | None = None,
        company_id: int | None = None,
    ) -> dict | list:
        """Update fields of an existing CRM task; only the given fields change."""
        body = {
            "title": title,
            "due_date": due_date,
            "done": done,
            "contact_id": contact_id,
            "company_id": company_id,
        }
        return await call(api, "PATCH", f"/tasks/{id}", json=body)

    @mcp.tool(name="delete")
    async def delete_task(id: int) -> dict | list:
        """Delete a CRM task permanently by id."""
        return await call(api, "DELETE", f"/tasks/{id}")

    @mcp.tool(name="list_open")
    async def list_open_tasks() -> dict | list:
        """List CRM tasks that are not done yet."""
        return await call(api, "GET", "/tasks", params={"done": "false", "limit": 200})

    @mcp.tool(name="list_done")
    async def list_done_tasks() -> dict | list:
        """List CRM tasks that are already completed."""
        return await call(api, "GET", "/tasks", params={"done": "true", "limit": 200})

    @mcp.tool(name="list_by_contact")
    async def list_tasks_by_contact(contact_id: int) -> dict | list:
        """List the CRM tasks linked to a given contact."""
        return await call(api, "GET", "/tasks", params={"contact_id": contact_id})

    @mcp.tool(name="list_by_company")
    async def list_tasks_by_company(company_id: int) -> dict | list:
        """List the CRM tasks linked to a given company."""
        return await call(api, "GET", "/tasks", params={"company_id": company_id})

    @mcp.tool(name="find_by_title")
    async def find_task_by_title(title: str) -> dict | list:
        """Search CRM tasks whose title contains the given text."""
        found = await fetch_all(api, "/tasks")
        if is_error(found):
            return found
        return [t for t in found if title.lower() in (t.get("title") or "").lower()]

    @mcp.tool(name="complete")
    async def complete_task(id: int) -> dict | list:
        """Mark a CRM task as done."""
        return await call(api, "PATCH", f"/tasks/{id}", json={"done": True})

    return mcp
