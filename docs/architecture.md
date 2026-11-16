# Architecture

Three services, one request path: browser -> agent -> gateway -> mock API.

## Gateway: sub-servers mounted by prefix

Each entity is its own FastMCP server, mounted with a namespace, so a tool `list` in `contacts` becomes `contacts_list`.

- [gateway/src/crm_gateway/server.py](../gateway/src/crm_gateway/server.py) mounts the sub-servers and adds `/health`.
- [gateway/src/crm_gateway/tools/](../gateway/src/crm_gateway/tools/) has one module per entity plus `reports`.
- Write tools are the ones whose action starts with `create`, `update`, `delete`, `move`, `merge` or `complete` (`WRITE_ACTIONS`).

## Gateway: structured errors

[http.py](../gateway/src/crm_gateway/http.py) wraps `httpx`. A failed call does not raise; it returns `{"error": true, "statusCode", "method", "url", "message", "responseBody"}`, so the model can read the problem and react. Network errors have `statusCode: null`.

## Gateway: two credentials

- `Authorization: Bearer <GATEWAY_SECRET>` proves the caller is the agent ([auth.py](../gateway/src/crm_gateway/auth.py), constant-time compare).
- `access-token: <user token>` is the end user, read per request ([headers.py](../gateway/src/crm_gateway/headers.py)) and forwarded to the mock API.
- [middleware.py](../gateway/src/crm_gateway/middleware.py) logs only tool name, duration and ok or error, never tokens or payloads.

## Agent: per-request MCP session

[mcp_tools.py](../agent/src/crm_agent/mcp_tools.py) opens one MCP session per chat request with the user's token and yields the tools. [app.py](../agent/src/crm_agent/app.py) holds that session in its own task, because the session's cancel scopes must be closed by the task that opened them, while the streaming response runs in another.

## Agent: dynamic tool binding

[build.py](../agent/src/crm_agent/build.py) passes the gateway tools to `DynamicToolBindingMiddleware` instead of `tools=`. The model sees `search_tools` and gets only the tools it asks for.

## Agent: human in the loop

`interrupt_on` is built from the write tools in `build_agent`. A checkpointer is required. The run pauses, [stream.py](../agent/src/crm_agent/stream.py) emits one `interrupt` line, and the client resumes with `Command(resume={"decisions": [...]})`. See [versions.md](versions.md) for the verified snippet.

## Agent: skills and subagent

[agent/skills/](../agent/skills/) holds four `SKILL.md` files, mounted at `/skills/` through a `CompositeBackend`; writes to `/skills/**` are denied. The `researcher` subagent gets only read tools, and its text is streamed as `think`.

## Agent: streaming

[stream.py](../agent/src/crm_agent/stream.py) maps `astream(subgraphs=True, stream_mode=["messages", "values"])` to NDJSON: main graph text is `token`, subgraph text is `think`, the todo list is `plan` when it changes, and pending interrupts end the stream as `interrupt`.

## Agent: thread ownership and checkpoints

[ownership.py](../agent/src/crm_agent/ownership.py): the first user to send on a thread claims it (atomic), others get 403. Only a hash of the token is used as the user id. With `ES_URL` set, checkpoints and ownership move to Elasticsearch.

## Request order

401 (bad header) -> 403 (other user's thread) -> open MCP tools -> 409 (resume without a pending interrupt, or message while one is pending) -> stream. If the gateway is down, the stream is `start` then one `error` line.
