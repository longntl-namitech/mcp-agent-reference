from pathlib import Path

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph_dynamic_tool_binding import DynamicToolBindingMiddleware

from .prompts import RESEARCHER_PROMPT, SYSTEM_PROMPT

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

WRITE_ACTIONS = ("create", "update", "delete", "move", "merge", "complete")


def is_write_tool(name: str) -> bool:
    _, _, action = name.partition("_")
    return action.startswith(WRITE_ACTIONS)


def build_agent(
    model: BaseChatModel | str, tools: list[BaseTool], checkpointer
) -> CompiledStateGraph:
    write_names = [t.name for t in tools if is_write_tool(t.name)]
    read_tools = [t for t in tools if not is_write_tool(t.name)]
    backend = CompositeBackend(
        default=StateBackend(),
        routes={"/skills/": FilesystemBackend(root_dir=SKILLS_DIR, virtual_mode=True)},
    )
    return create_deep_agent(
        model,
        system_prompt=SYSTEM_PROMPT,
        middleware=[DynamicToolBindingMiddleware(tools)],
        subagents=[
            {
                "name": "researcher",
                "description": "Read-only CRM lookups: facts about a company, contact or deal.",
                "system_prompt": RESEARCHER_PROMPT,
                "tools": read_tools,
            }
        ],
        skills=["/skills/"],
        backend=backend,
        permissions=[FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")],
        interrupt_on={n: {"allowed_decisions": ["approve", "reject"]} for n in write_names},
        checkpointer=checkpointer,
    )
