"""HTTP routes for the target AI application."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.agent import AgentError, CustomerSupportAgent
from app.config import model_config
from app.ollama_client import OllamaClient
from app.rag.retriever import KnowledgeRetriever


logger = logging.getLogger(__name__)
router = APIRouter()
try:
    retriever = KnowledgeRetriever()
    agent: CustomerSupportAgent | None = CustomerSupportAgent(retriever, OllamaClient(model_config()))
    initialization_error: str | None = None
except Exception:
    logger.exception("RAG initialization failed")
    retriever = None
    agent = None
    initialization_error = "The local knowledge base is unavailable"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str
    metadata: dict[str, Any]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if agent is None:
        raise HTTPException(status_code=503, detail=initialization_error)
    try:
        return ChatResponse(**agent.respond(request.message))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
