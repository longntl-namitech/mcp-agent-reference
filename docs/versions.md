# Versions

Resolved by `uv.lock` on 2026-11-13.

| Package | Version |
| --- | --- |
| deepagents | 0.7.37 |
| fastmcp | 3.4.11 |
| mcp | 1.30.0 |
| langchain-mcp-adapters | 0.3.2 |
| langgraph | 1.2.21 |
| langchain | 1.5.0 |
| langchain-core | 1.8.0 |
| langchain-openai | 1.7.4 |
| fastapi | 0.162.5 |
| uvicorn | 0.54.0 |
| pydantic-settings | 2.16.2 |
| elasticsearch | 9.5.1 |
| langgraph-dynamic-tool-binding | 0.1.0 (git, pinned commit) |
| langgraph-checkpoint-elasticsearch | 0.1.0 (git, tag v0.1.0) |

## Pin: fastmcp 3.x and mcp 1.x

The latest fastmcp (4.1.8) requires `mcp>=2.3.0`. langchain-mcp-adapters 0.3.2 requires `mcp<2.0.0`, and 0.3.1 fails at import with mcp 2.x
(`ImportError: cannot import name 'RequestContext' from 'mcp.shared.context'`). So `mcp` is pinned to `>=1.24,<2` in `gateway` and `agent`,
which forces fastmcp to the latest 3.x (`>=3.4,<4`). Revisit when langchain-mcp-adapters supports mcp 2.

## fastmcp: mount a sub-server with a prefix

Signature (3.4.11): `FastMCP.mount(server, namespace=None, as_proxy=None, tool_names=None, prefix=None)`. Use `namespace`.

```python
from fastmcp import FastMCP

contacts = FastMCP("contacts")

@contacts.tool(name="list")
def list_contacts() -> list[str]: ...

gateway = FastMCP("gateway")
gateway.mount(contacts, namespace="contacts")
# client.list_tools() -> ["contacts_list", ...]
```

Verified over HTTP: sub-server tool `list` mounted at `contacts` is exposed as `contacts_list`.

## fastmcp: custom headers from client to tool

Client side, HTTP transport takes `headers`:

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport(
    "http://127.0.0.1:8000/mcp",
    headers={"access-token": "demo-token-alice"},
)
async with Client(transport) as client:
    await client.call_tool("contacts_list", {})
```

Tool side, read them with `get_http_headers` (names are lower-case). By default it drops some headers such as `authorization`;
pass `include` to get them.

```python
from fastmcp.server.dependencies import get_http_headers

token = get_http_headers().get("access-token")
auth = get_http_headers(include={"authorization"}).get("authorization")
```

Verified: both `access-token` and `Authorization` reached the tool through a prefix-mounted sub-server.

## langchain-mcp-adapters with mcp 1.30

Works against a FastMCP HTTP server, headers included:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

mc = MultiServerMCPClient({
    "gateway": {
        "transport": "http",
        "url": "http://127.0.0.1:8000/mcp",
        "headers": {"access-token": "demo-token-alice"},
    }
})
tools = await mc.get_tools()  # includes contacts_list
```

## deepagents: human in the loop

`create_deep_agent(..., interrupt_on={...}, checkpointer=...)` adds langchain's `HumanInTheLoopMiddleware` in the default
`batched` mode (deepagents does not pass `interrupt_mode`). A checkpointer is required.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

agent = create_deep_agent(
    model,
    tools=tools,
    interrupt_on={"deals_delete": {"allowed_decisions": ["approve", "reject"]}},  # or True
    checkpointer=InMemorySaver(),
)
config = {"configurable": {"thread_id": "t1"}, "recursion_limit": 100}
```

The pause is a LangGraph interrupt. Its value is one request per model turn:

```python
{"action_requests": [{"name": "deals_delete", "args": {...}, "description": "..."}],
 "review_configs": [{"action_name": "deals_delete", "allowed_decisions": ["approve", "reject"]}]}
```

Resume with one decision per action request, in the same order:

```python
# approve
agent.astream(Command(resume={"decisions": [{"type": "approve"}]}), config)
# reject (message is optional and is returned to the model)
agent.astream(Command(resume={"decisions": [{"type": "reject", "message": "Not allowed."}]}), config)
```

Other decision types: `edit` (with edited `args`) and `respond` (with `message`), when listed in `allowed_decisions`.
Source: `langchain/agents/middleware/human_in_the_loop.py`.
