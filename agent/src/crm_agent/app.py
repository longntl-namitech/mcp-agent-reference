from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from .build import build_agent
from .mcp_tools import open_mcp_tools
from .ownership import EsOwnership, MemoryOwnership, Ownership, user_id_for
from .settings import Settings
from .stream import _line, stream_ndjson

STATIC_DIR = Path(__file__).parent / "static"


class Resume(BaseModel):
    decision: Literal["approve", "reject"]
    message: str | None = None


class ChatRequest(BaseModel):
    thread_id: str
    message: str | None = None
    resume: Resume | None = None


def _bearer(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token.strip()


def create_app(
    settings: Settings,
    *,
    model=None,
    tools_opener: Callable | None = None,
    checkpointer=None,
    ownership: Ownership | None = None,
) -> FastAPI:
    opener = tools_opener or open_mcp_tools
    deps = {"checkpointer": checkpointer, "ownership": ownership}
    if deps["checkpointer"] is None and settings.es_url is None:
        deps["checkpointer"] = MemorySaver()
    if deps["ownership"] is None and settings.es_url is None:
        deps["ownership"] = MemoryOwnership()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        client = None
        if deps["checkpointer"] is None or deps["ownership"] is None:
            from elasticsearch import AsyncElasticsearch
            from langgraph_checkpoint_elasticsearch import (
                AsyncElasticsearchSaver,
                SessionOwnershipStore,
            )

            client = AsyncElasticsearch(settings.es_url, api_key=settings.es_api_key)
            if deps["checkpointer"] is None:
                saver = AsyncElasticsearchSaver(client)
                await saver.setup()
                deps["checkpointer"] = saver
            if deps["ownership"] is None:
                store = SessionOwnershipStore(client)
                await store.setup()
                deps["ownership"] = EsOwnership(store)
        try:
            yield
        finally:
            if client is not None:
                await client.close()

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.post("/chat/stream")
    async def chat_stream(body: ChatRequest, authorization: str | None = Header(default=None)):
        token = _bearer(authorization)
        if not await deps["ownership"].claim(body.thread_id, user_id_for(token)):
            raise HTTPException(status_code=403, detail="Thread belongs to another user")
        if (body.message is None) == (body.resume is None):
            raise HTTPException(status_code=422, detail="Send exactly one of message or resume")

        stack = AsyncExitStack()
        headers = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
        media = "application/x-ndjson"
        try:
            tools = await stack.enter_async_context(opener(settings, token))
            agent = build_agent(model or settings.model, tools, deps["checkpointer"])
            config = {"configurable": {"thread_id": body.thread_id}, "recursion_limit": 100}
            pending = bool((await agent.aget_state(config)).interrupts)
        except Exception as exc:
            await stack.aclose()
            error = f"{type(exc).__name__}: {exc}"[:200]

            async def failed():
                yield _line("start", "")
                yield _line("error", error)

            return StreamingResponse(failed(), media_type=media, headers=headers)

        if body.resume is not None and not pending:
            await stack.aclose()
            raise HTTPException(status_code=409, detail="No pending interrupt to resume")
        if body.message is not None and pending:
            await stack.aclose()
            raise HTTPException(status_code=409, detail="Resolve the pending interrupt first")

        if body.resume is not None:
            decision = {"type": body.resume.decision}
            if body.resume.decision == "reject" and body.resume.message:
                decision["message"] = body.resume.message
            graph_input = Command(resume={"decisions": [decision]})
        else:
            graph_input = {"messages": [{"role": "user", "content": body.message}]}

        async def body_stream():
            try:
                async for line in stream_ndjson(agent, graph_input, config):
                    yield line
            finally:
                await stack.aclose()

        return StreamingResponse(body_stream(), media_type=media, headers=headers)

    return app
