from datetime import date

from fastmcp import FastMCP

from ..http import ApiClient, is_error
from ._common import call, fetch_all

STAGES = ("lead", "qualified", "proposal", "won", "lost")


def build_reports(api: ApiClient) -> FastMCP:
    mcp = FastMCP("reports")

    @mcp.tool(name="pipeline_by_stage")
    async def pipeline_by_stage() -> dict | list:
        """Sales pipeline report: number of CRM deals and total amount in each stage."""
        deals = await fetch_all(api, "/deals")
        if is_error(deals):
            return deals
        report = {s: {"stage": s, "count": 0, "total_amount": 0.0} for s in STAGES}
        for d in deals:
            row = report[d["stage"]]
            row["count"] += 1
            row["total_amount"] += d["amount"]
        return list(report.values())

    @mcp.tool(name="won_revenue")
    async def won_revenue() -> dict | list:
        """Revenue report: total amount and count of CRM deals that were won."""
        deals = await fetch_all(api, "/deals", {"stage": "won"})
        if is_error(deals):
            return deals
        return {"count": len(deals), "total_amount": sum(d["amount"] for d in deals)}

    @mcp.tool(name="top_deals")
    async def top_deals(n: int = 5) -> dict | list:
        """Report of the biggest open CRM deals by amount, largest first."""
        deals = await fetch_all(api, "/deals")
        if is_error(deals):
            return deals
        open_deals = [d for d in deals if d["stage"] not in ("won", "lost")]
        return sorted(open_deals, key=lambda d: d["amount"], reverse=True)[:n]

    @mcp.tool(name="company_activity")
    async def company_activity(company_id: int) -> dict | list:
        """Activity report of a CRM company: its notes and tasks, newest first."""
        return await call(api, "GET", f"/companies/{company_id}/activities")

    @mcp.tool(name="overdue_tasks")
    async def overdue_tasks(today: str | None = None) -> dict | list:
        """Report of overdue CRM tasks: not done and due before today (YYYY-MM-DD)."""
        cutoff = today or date.today().isoformat()
        tasks = await fetch_all(api, "/tasks", {"done": "false"})
        if is_error(tasks):
            return tasks
        return [t for t in tasks if t.get("due_date") and t["due_date"] < cutoff]

    @mcp.tool(name="contact_overview")
    async def contact_overview(contact_id: int) -> dict | list:
        """Overview report of one CRM contact: the contact with its deals, tasks and notes."""
        contact = await call(api, "GET", f"/contacts/{contact_id}")
        if is_error(contact):
            return contact
        parts = {}
        for name in ("deals", "tasks", "notes"):
            found = await call(api, "GET", f"/{name}", params={"contact_id": contact_id})
            if is_error(found):
                return found
            parts[name] = found
        return {"contact": contact, **parts}

    return mcp
