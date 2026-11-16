import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk


def _line(type_: str, content: str) -> str:
    return json.dumps({"type": type_, "content": content}) + "\n"


def _text(message: Any) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )


def _render_todos(todos: list[dict]) -> str:
    return "\n".join(f"[{t.get('status')}] {t.get('content')}" for t in todos)


async def stream_ndjson(agent, graph_input, config) -> AsyncIterator[str]:
    """Run the agent and yield NDJSON lines; tool calls and results are never emitted."""
    yield _line("start", "")
    last_plan = None
    try:
        async for ns, mode, data in agent.astream(
            graph_input, config, subgraphs=True, stream_mode=["messages", "values"]
        ):
            if mode == "messages":
                message, _meta = data
                if not isinstance(message, AIMessage | AIMessageChunk):
                    continue
                text = _text(message)
                if text:
                    yield _line("think" if ns else "token", text)
            elif mode == "values" and not ns and isinstance(data, dict):
                todos = data.get("todos")
                if todos:
                    plan = _render_todos(todos)
                    if plan != last_plan:
                        last_plan = plan
                        yield _line("plan", plan)
        state = await agent.aget_state(config)
        pending = [req for i in state.interrupts for req in i.value["action_requests"]]
        if pending:
            payload = [{"name": r["name"], "args": r["args"]} for r in pending]
            yield _line("interrupt", json.dumps(payload))
    except Exception as exc:
        yield _line("error", f"{type(exc).__name__}: {exc}"[:200])
