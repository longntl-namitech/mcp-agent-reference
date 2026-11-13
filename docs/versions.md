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

- Detecting the pause while streaming: with `stream_mode="updates"` a chunk `{"__interrupt__": (Interrupt, ...)}` arrives and the
  stream then ends. `chunk["__interrupt__"][0].value` is `{"action_requests": [{"name", "args", "description"}], "review_configs": [...]}`.
- After the stream, `await agent.aget_state(config)` also shows it: `state.interrupts` holds the same values and `state.next` is
  `("HumanInTheLoopMiddleware.after_model",)`.
- Resume with `Command(resume={"decisions": [...]})`, one decision per action request in the same order: `{"type": "approve"}` or
  `{"type": "reject", "message": "..."}` (message optional, returned to the model). `edit` and `respond` also exist when listed in
  `allowed_decisions`. Source: `langchain/agents/middleware/human_in_the_loop.py`.

Verified snippet (scripted model and fake tool, no API key). Run it as a throwaway script:

```python
import asyncio

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

CALLS = []


@tool
def deals_delete(deal_id: str) -> str:
    """Delete a deal."""
    CALLS.append(deal_id)
    return f"deleted {deal_id}"


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def make_agent():
    call = {"name": "deals_delete", "args": {"deal_id": "d1"}, "id": "c1"}
    msgs = iter([AIMessage(content="", tool_calls=[call]), AIMessage(content="done")])
    return create_deep_agent(
        ScriptedModel(messages=msgs),
        tools=[deals_delete],
        interrupt_on={"deals_delete": {"allowed_decisions": ["approve", "reject"]}},
        checkpointer=InMemorySaver(),
    )


async def run(decision):
    agent = make_agent()
    config = {"configurable": {"thread_id": f"t-{decision['type']}"}, "recursion_limit": 100}
    inp = {"messages": [{"role": "user", "content": "delete d1"}]}
    async for chunk in agent.astream(inp, config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            reqs = chunk["__interrupt__"][0].value["action_requests"]
            print("PAUSED", [{"name": r["name"], "args": r["args"]} for r in reqs])
    state = await agent.aget_state(config)
    print("PENDING", [i.value["action_requests"][0]["name"] for i in state.interrupts], state.next)
    async for chunk in agent.astream(
        Command(resume={"decisions": [decision]}), config, stream_mode="updates"
    ):
        for node, upd in chunk.items():
            if node == "tools":
                print("TOOL RESULT", upd["messages"][0].content)
    print("tool calls executed:", CALLS)


async def main():
    await run({"type": "approve"})
    CALLS.clear()
    await run({"type": "reject", "message": "Not allowed."})


asyncio.run(main())
```

Output:

```text
PAUSED [{'name': 'deals_delete', 'args': {'deal_id': 'd1'}}]
PENDING ['deals_delete'] ('HumanInTheLoopMiddleware.after_model',)
TOOL RESULT deleted d1
tool calls executed: ['d1']
PAUSED [{'name': 'deals_delete', 'args': {'deal_id': 'd1'}}]
PENDING ['deals_delete'] ('HumanInTheLoopMiddleware.after_model',)
tool calls executed: []
```
