from typing import Literal

from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all

Stage = Literal["lead", "qualified", "proposal", "won", "lost"]


def build_deals(api: ApiClient) -> FastMCP:
    mcp = FastMCP("deals")

    @mcp.tool(name="list")
    async def list_deals(limit: int = 50, offset: int = 0) -> dict | list:
        """List CRM deals (sales opportunities), one page at a time, ordered by id."""
        return await call(api, "GET", "/deals", params={"limit": limit, "offset": offset})

    @mcp.tool(name="get")
    async def get_deal(id: int) -> dict | list:
        """Get one CRM deal by id, with title, amount, stage, company and contact."""
        return await call(api, "GET", f"/deals/{id}")

    @mcp.tool(name="create")
    async def create_deal(
        title: str,
        amount: float = 0,
        stage: Stage = "lead",
        company_id: int | None = None,
        contact_id: int | None = None,
    ) -> dict | list:
        """Create a new CRM deal with title, amount and pipeline stage."""
        body = {
            "title": title,
            "amount": amount,
            "stage": stage,
            "company_id": company_id,
            "contact_id": contact_id,
        }
        return await call(api, "POST", "/deals", json=body)

    @mcp.tool(name="update")
    async def update_deal(
        id: int,
        title: str | None = None,
        amount: float | None = None,
        stage: Stage | None = None,
        company_id: int | None = None,
        contact_id: int | None = None,
    ) -> dict | list:
        """Update fields of an existing CRM deal; only the given fields change."""
        body = {
            "title": title,
            "amount": amount,
            "stage": stage,
            "company_id": company_id,
            "contact_id": contact_id,
        }
        return await call(api, "PATCH", f"/deals/{id}", json=body)

    @mcp.tool(name="delete")
    async def delete_deal(id: int) -> dict | list:
        """Delete a CRM deal permanently by id."""
        return await call(api, "DELETE", f"/deals/{id}")

    @mcp.tool(name="list_by_stage")
    async def list_deals_by_stage(stage: Stage) -> dict | list:
        """List CRM deals in one pipeline stage: lead, qualified, proposal, won or lost."""
        return await call(api, "GET", "/deals", params={"stage": stage})

    @mcp.tool(name="list_by_company")
    async def list_deals_by_company(company_id: int) -> dict | list:
        """List the CRM deals of a given company."""
        return await call(api, "GET", "/deals", params={"company_id": company_id})

    @mcp.tool(name="list_by_contact")
    async def list_deals_by_contact(contact_id: int) -> dict | list:
        """List the CRM deals linked to a given contact."""
        return await call(api, "GET", "/deals", params={"contact_id": contact_id})

    @mcp.tool(name="list_open")
    async def list_open_deals() -> dict | list:
        """List open CRM deals, meaning every deal not yet won or lost."""
        found = await fetch_all(api, "/deals")
        if is_error(found):
            return found
        return [d for d in found if d.get("stage") not in ("won", "lost")]

    @mcp.tool(name="find_by_title")
    async def find_deal_by_title(title: str) -> dict | list:
        """Search CRM deals whose title contains the given text."""
        found = await fetch_all(api, "/deals")
        if is_error(found):
            return found
        return [d for d in found if title.lower() in (d.get("title") or "").lower()]

    @mcp.tool(name="move_stage")
    async def move_deal_stage(id: int, stage: Stage) -> dict | list:
        """Move a CRM deal to another pipeline stage: lead, qualified, proposal, won or lost."""
        return await call(api, "POST", f"/deals/{id}/stage", json={"stage": stage})

    return mcp
