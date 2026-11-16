from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all


def build_companies(api: ApiClient) -> FastMCP:
    mcp = FastMCP("companies")

    @mcp.tool(name="list")
    async def list_companies(limit: int = 50, offset: int = 0) -> dict | list:
        """List CRM companies (accounts), one page at a time, ordered by id."""
        return await call(api, "GET", "/companies", params={"limit": limit, "offset": offset})

    @mcp.tool(name="get")
    async def get_company(id: int) -> dict | list:
        """Get one CRM company by id, with name, industry and website."""
        return await call(api, "GET", f"/companies/{id}")

    @mcp.tool(name="create")
    async def create_company(
        name: str, industry: str | None = None, website: str | None = None
    ) -> dict | list:
        """Create a new CRM company, optionally with industry and website."""
        body = {"name": name, "industry": industry, "website": website}
        return await call(api, "POST", "/companies", json=body)

    @mcp.tool(name="update")
    async def update_company(
        id: int,
        name: str | None = None,
        industry: str | None = None,
        website: str | None = None,
    ) -> dict | list:
        """Update fields of an existing CRM company; only the given fields change."""
        body = {"name": name, "industry": industry, "website": website}
        return await call(api, "PATCH", f"/companies/{id}", json=body)

    @mcp.tool(name="delete")
    async def delete_company(id: int) -> dict | list:
        """Delete a CRM company permanently by id."""
        return await call(api, "DELETE", f"/companies/{id}")

    @mcp.tool(name="find_by_name")
    async def find_company_by_name(name: str) -> dict | list:
        """Search CRM companies whose name contains the given text."""
        return await call(api, "GET", "/companies", params={"name": name})

    @mcp.tool(name="list_by_industry")
    async def list_companies_by_industry(industry: str) -> dict | list:
        """List CRM companies in an exact industry, for example Software or Retail."""
        return await call(api, "GET", "/companies", params={"industry": industry})

    @mcp.tool(name="find_by_website")
    async def find_company_by_website(website: str) -> dict | list:
        """Search CRM companies whose website contains the given domain text."""
        found = await fetch_all(api, "/companies")
        if is_error(found):
            return found
        return [c for c in found if website.lower() in (c.get("website") or "").lower()]

    @mcp.tool(name="get_activities")
    async def get_company_activities(id: int) -> dict | list:
        """List recent notes and tasks of a CRM company and its contacts, newest first."""
        return await call(api, "GET", f"/companies/{id}/activities")

    return mcp
