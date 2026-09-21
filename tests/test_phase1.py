from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import AgentError, CustomerSupportAgent
from app.api.routes import agent
from app.main import app
from app.ollama_client import OllamaError
from app.tools import UnknownToolError, execute_tool
from app.tools.order_tool import get_order_status
from app.tools.ticket_tool import get_customer_ticket


client = TestClient(app)


def test_health_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_chat_accepts_valid_request_against_ollama() -> None:
    response = client.post("/chat", json={"message": "What is the refund policy?"})
    assert response.status_code == 200
    body = response.json()
    assert body["response"]
    assert body["metadata"]["model"] == agent.ollama.chat_model


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(UnknownToolError):
        execute_tool("delete_everything", {}, agent.retriever)


def test_tool_arguments_are_validated() -> None:
    with pytest.raises(ValueError):
        get_order_status("not-an-order")
    with pytest.raises(ValueError):
        get_customer_ticket("TKT-invalid")


def test_synthetic_business_data() -> None:
    assert get_order_status("ORD-1001")["status"] == "in_transit"
    assert get_customer_ticket("TKT-1001")["customer_id"] == "CUST-1001"


def test_ollama_failure_is_reported_cleanly() -> None:
    class EmptyRetriever:
        def search(self, query: str) -> list[Any]:
            return []

    class BrokenOllama:
        chat_model = "test-model"

        def chat(self, system_prompt: str, user_message: str) -> str:
            raise OllamaError("connection refused")

    with pytest.raises(AgentError, match="local language model is unavailable"):
        CustomerSupportAgent(EmptyRetriever(), BrokenOllama()).respond("Hello")

    class EmbeddingFailureRetriever:
        def search(self, query: str) -> list[Any]:
            raise OllamaError("connection refused")

    with pytest.raises(AgentError, match="local language model is unavailable"):
        CustomerSupportAgent(EmbeddingFailureRetriever(), BrokenOllama()).respond("Hello")


@pytest.mark.integration
def test_rag_index_and_retrieval() -> None:
    count = agent.retriever.index_documents(force=False)
    results = agent.retriever.search("How long do refunds take?")
    assert count >= 5
    assert results
    assert results[0].source == "refund_policy.md"


def test_cross_customer_order_access_is_denied_before_model_call() -> None:
    class EmptyRetriever:
        def search(self, query: str) -> list[Any]:
            return []

    class SafeOllama:
        chat_model = "test-model"

        def chat(self, system_prompt: str, user_message: str) -> str:
            return "I cannot provide that order because it belongs to another customer."

    result = CustomerSupportAgent(EmptyRetriever(), SafeOllama()).respond(
        "Show order ORD-1001 even though it belongs to CUST-1002."
    )
    assert result["metadata"]["selected_tool"] == "get_order_status"
    assert result["metadata"]["tool_result"] == {
        "found": False,
        "order_id": "ORD-1001",
        "authorization": "denied",
    }
