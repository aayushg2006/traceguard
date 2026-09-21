"""Explicit mock-tool registry for the target application."""

from typing import Any, Callable

from app.tools.knowledge_tool import search_knowledge_base
from app.tools.order_tool import get_order_status
from app.tools.ticket_tool import create_support_ticket, get_customer_ticket


class UnknownToolError(ValueError):
    pass


def build_tool_registry(retriever: Any) -> dict[str, Callable[..., dict[str, Any]]]:
    return {
        "get_customer_ticket": get_customer_ticket,
        "get_order_status": get_order_status,
        "create_support_ticket": create_support_ticket,
        "search_knowledge_base": lambda query: search_knowledge_base(query, retriever),
    }


def execute_tool(name: str, arguments: dict[str, Any], retriever: Any) -> dict[str, Any]:
    registry = build_tool_registry(retriever)
    if name not in registry:
        raise UnknownToolError(f"Unsupported tool: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    try:
        return registry[name](**arguments)
    except TypeError as exc:
        raise ValueError("Invalid arguments for requested tool") from exc
