from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all


def build_contacts(api: ApiClient) -> FastMCP:
    mcp = FastMCP("contacts")

    @mcp.tool(name="list")
    async def list_contacts(limit: int = 50, offset: int = 0) -> dict | list:
        """List CRM contacts (people), one page at a time, ordered by id."""
        return await call(api, "GET", "/contacts", params={"limit": limit, "offset": offset})

    @mcp.tool(name="get")
    async def get_contact(id: int) -> dict | list:
        """Get one CRM contact by id, with name, email, phone and company."""
        return await call(api, "GET", f"/contacts/{id}")

    @mcp.tool(name="create")
    async def create_contact(
        name: str,
        email: str | None = None,
        phone: str | None = None,
        company_id: int | None = None,
    ) -> dict | list:
        """Create a new CRM contact, optionally with email, phone and company."""
        body = {"name": name, "email": email, "phone": phone, "company_id": company_id}
        return await call(api, "POST", "/contacts", json=body)

    @mcp.tool(name="update")
    async def update_contact(
        id: int,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        company_id: int | None = None,
    ) -> dict | list:
        """Update fields of an existing CRM contact; only the given fields change."""
        body = {"name": name, "email": email, "phone": phone, "company_id": company_id}
        return await call(api, "PATCH", f"/contacts/{id}", json=body)

    @mcp.tool(name="delete")
    async def delete_contact(id: int) -> dict | list:
        """Delete a CRM contact permanently by id."""
        return await call(api, "DELETE", f"/contacts/{id}")

    @mcp.tool(name="find_by_email")
    async def find_contact_by_email(email: str) -> dict | list:
        """Find CRM contacts by exact email address."""
        return await call(api, "GET", "/contacts", params={"email": email})

    @mcp.tool(name="find_by_name")
    async def find_contact_by_name(name: str) -> dict | list:
        """Search CRM contacts whose name contains the given text."""
        return await call(api, "GET", "/contacts", params={"name": name})

    @mcp.tool(name="find_by_phone")
    async def find_contact_by_phone(phone: str) -> dict | list:
        """Search CRM contacts whose phone number contains the given digits."""
        found = await fetch_all(api, "/contacts")
        if is_error(found):
            return found
        return [c for c in found if phone in (c.get("phone") or "")]

    @mcp.tool(name="list_by_company")
    async def list_contacts_by_company(company_id: int) -> dict | list:
        """List the CRM contacts that work at a given company."""
        return await call(api, "GET", "/contacts", params={"company_id": company_id})

    @mcp.tool(name="list_without_company")
    async def list_contacts_without_company() -> dict | list:
        """List CRM contacts that are not linked to any company."""
        found = await fetch_all(api, "/contacts")
        if is_error(found):
            return found
        return [c for c in found if c.get("company_id") is None]

    @mcp.tool(name="merge")
    async def merge_contacts(keep_id: int, merge_id: int) -> dict | list:
        """Merge duplicate CRM contacts: notes, tasks and deals of merge_id move to keep_id."""
        return await call(
            api, "POST", "/contacts/merge", json={"keep_id": keep_id, "merge_id": merge_id}
        )

    return mcp
