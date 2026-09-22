"""Customer-support orchestration with explicit tool selection."""

import logging
import re
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT
from app.ollama_client import OllamaClient, OllamaError
from app.rag.retriever import KnowledgeRetriever
from app.tools import execute_tool


logger = logging.getLogger(__name__)


class AgentError(RuntimeError):
    pass


class CustomerSupportAgent:
    def __init__(self, retriever: KnowledgeRetriever, ollama: OllamaClient) -> None:
        self.retriever = retriever
        self.ollama = ollama

    def _select_tool(self, message: str) -> tuple[str, dict[str, Any]] | None:
        order = re.search(r"\bORD-\d{4}\b", message.upper())
        ticket = re.search(r"\bTKT-\d{4}\b", message.upper())
        customer = re.search(r"\bCUST-\d{4}\b", message.upper())
        lower = message.lower()
        if order and any(word in lower for word in ("order", "delivery", "shipping", "status")):
            return "get_order_status", {"order_id": order.group(0)}
        if ticket and any(word in lower for word in ("ticket", "case", "support")):
            return "get_customer_ticket", {"ticket_id": ticket.group(0)}
        if any(word in lower for word in ("create ticket", "open ticket", "contact support")):
            if not customer:
                return None
            return "create_support_ticket", {"customer_id": customer.group(0), "subject": message[:120]}
        return None

    def respond(self, message: str) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        message = message.strip()
        selected = self._select_tool(message)
        tool_name: str | None = None
        tool_arguments: dict[str, Any] | None = None
        tool_result: dict[str, Any] | None = None
        if selected:
            tool_name, tool_arguments = selected
            logger.info("Selected mock tool: %s", tool_name)
            try:
                tool_result = execute_tool(tool_name, tool_arguments, self.retriever)
            except ValueError as exc:
                raise AgentError(str(exc)) from exc
            if tool_name == "get_order_status" and tool_result.get("found") is True:
                requester = re.search(r"\bCUST-\d{4}\b", message.upper())
                owner = tool_result.get("customer_id")
                if not requester or owner != requester.group(0):
                    reason = "missing_customer_verification" if not requester else "cross_customer_access"
                    logger.warning("Denied order access (%s): requester=%s owner=%s", reason, requester.group(0) if requester else None, owner)
                    tool_result = {
                        "found": False,
                        "order_id": tool_result.get("order_id"),
                        "authorization": "denied",
                        "reason": reason,
                    }
        try:
            retrieved = self.retriever.search(message)
        except OllamaError as exc:
            logger.exception("Ollama embedding request failed")
            raise AgentError("The local language model is unavailable") from exc
        context_parts = [f"Source: {item.source}\n{item.text}" for item in retrieved]
        if tool_result:
            context_parts.append(f"Authorized tool result ({tool_name}): {tool_result}")
        context = "\n\n---\n\n".join(context_parts) or "No approved knowledge matched this request."
        prompt = f"Approved reference data:\n{context}\n\nUser request:\n{message}"
        logger.info("Invoking model %s", self.ollama.chat_model)
        try:
            response = self.ollama.chat(SYSTEM_PROMPT, prompt)
        except OllamaError as exc:
            logger.exception("Ollama invocation failed")
            raise AgentError("The local language model is unavailable") from exc
        return {
            "response": response,
            "metadata": {
                "model": self.ollama.chat_model,
                "retrieved_documents": [item.source for item in retrieved],
                "selected_tool": tool_name,
                "tool_arguments": tool_arguments,
                "tool_result": tool_result,
            },
        }
