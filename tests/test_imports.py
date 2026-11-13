def test_packages_import():
    import crm_agent, crm_gateway, mock_crm  # noqa: F401
    import deepagents, fastmcp, langchain_mcp_adapters  # noqa: F401
    from langgraph_dynamic_tool_binding import DynamicToolBindingMiddleware  # noqa: F401
