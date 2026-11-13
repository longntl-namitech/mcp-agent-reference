from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all


def build_notes(api: ApiClient) -> FastMCP:
    mcp = FastMCP("notes")

    @mcp.tool(name="list")
    async def list_notes(limit: int = 50, offset: int = 0) -> dict | list:
        """List CRM notes (call and meeting logs), one page at a time, ordered by id."""
        return await call(api, "GET", "/notes", params={"limit": limit, "offset": offset})

    @mcp.tool(name="get")
    async def get_note(id: int) -> dict | list:
        """Get one CRM note by id, with body, date and linked contact or company."""
        return await call(api, "GET", f"/notes/{id}")

    @mcp.tool(name="create")
    async def create_note(
        body: str, contact_id: int | None = None, company_id: int | None = None
    ) -> dict | list:
        """Create a new CRM note about a contact or company; the date is set automatically."""
        payload = {"body": body, "contact_id": contact_id, "company_id": company_id}
        return await call(api, "POST", "/notes", json=payload)

    @mcp.tool(name="update")
    async def update_note(
        id: int,
        body: str | None = None,
        contact_id: int | None = None,
        company_id: int | None = None,
    ) -> dict | list:
        """Update fields of an existing CRM note; only the given fields change."""
        payload = {"body": body, "contact_id": contact_id, "company_id": company_id}
        return await call(api, "PATCH", f"/notes/{id}", json=payload)

    @mcp.tool(name="delete")
    async def delete_note(id: int) -> dict | list:
        """Delete a CRM note permanently by id."""
        return await call(api, "DELETE", f"/notes/{id}")

    @mcp.tool(name="list_by_contact")
    async def list_notes_by_contact(contact_id: int) -> dict | list:
        """List the CRM notes written about a given contact."""
        return await call(api, "GET", "/notes", params={"contact_id": contact_id})

    @mcp.tool(name="list_by_company")
    async def list_notes_by_company(company_id: int) -> dict | list:
        """List the CRM notes written about a given company."""
        return await call(api, "GET", "/notes", params={"company_id": company_id})

    @mcp.tool(name="search_text")
    async def search_notes_text(text: str) -> dict | list:
        """Search CRM notes whose body contains the given text."""
        found = await fetch_all(api, "/notes")
        if is_error(found):
            return found
        return [n for n in found if text.lower() in (n.get("body") or "").lower()]

    return mcp
