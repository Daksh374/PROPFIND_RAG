"""
chat.py — SSE streaming chat endpoint + confirmation handler.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.graph import run_agent, handle_confirmed_node, handle_cancelled_node
from app.agent.memory import get_user_memory, extract_and_store_memory
from app.rag.pipeline import rag_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# ─── Request/response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    user_identifier: str = "anonymous"
    mode: str = "auto"  # "rag" | "agent" | "auto"
    chat_history: list[dict] | None = None


class ConfirmRequest(BaseModel):
    user_identifier: str = "anonymous"
    decision: str  # "confirmed" | "cancelled"
    pending_confirmation: dict


# ─── Intent detection (lightweight) ──────────────────────────────────────────

_AGENT_KEYWORDS = {
    "schedule", "visit", "book", "inquiry", "inquire",
    "compare", "pdf", "report", "estimate", "fair price",
    "contact", "owner", "send message", "cancel", "remove", "delete",
}


def _should_use_agent(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _AGENT_KEYWORDS)


def _resolve_mode(req: ChatRequest) -> str:
    mode = (req.mode or "auto").lower().strip()
    if mode not in {"auto", "rag", "agent"}:
        raise HTTPException(status_code=400, detail="mode must be one of: auto, rag, agent")
    if mode == "auto":
        return "agent" if _should_use_agent(req.message) else "rag"
    return mode


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    Returns SSE stream with text/event-stream content type.
    Emits events: engine, sources, token, done, error, confirmation_required
    """
    engine = _resolve_mode(req)

    # Store memory heuristics
    extract_and_store_memory(req.user_identifier, req.message)
    user_memory = get_user_memory(req.user_identifier)

    if engine == "agent":
        return StreamingResponse(
            _agent_sse(req, user_memory),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return StreamingResponse(
            _rag_sse(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


async def _rag_sse(req: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream RAG answer with sources."""
    try:
        yield f"event: engine\ndata: {json.dumps({'engine': 'rag'})}\n\n"
        token_gen, chunks = rag_stream(
            query=req.message,
            chat_history=req.chat_history,
        )

        # Emit sources first
        sources_data = [
            {
                "property_id": c.get("property_id"),
                "locality": c.get("locality"),
                "listing_type": c.get("listing_type"),
                "chunk_type": c.get("chunk_type"),
                "score": c.get("score"),
            }
            for c in chunks
        ]
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        # Stream tokens
        for token in token_gen:
            yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

        yield f"event: done\ndata: {json.dumps({'engine': 'rag', 'source_count': len(chunks)})}\n\n"

    except Exception as e:
        logger.exception("RAG SSE error")
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


async def _agent_sse(req: ChatRequest, user_memory: dict) -> AsyncGenerator[str, None]:
    """Run agent and stream result."""
    try:
        yield f"event: engine\ndata: {json.dumps({'engine': 'agent'})}\n\n"
        yield f"event: thinking\ndata: {json.dumps({'message': 'Agent is processing...'})}\n\n"

        result = run_agent(
            user_message=req.message,
            user_identifier=req.user_identifier,
            user_memory=user_memory,
            chat_history=req.chat_history,
        )

        if result["type"] == "confirmation_required":
            yield f"event: confirmation_required\ndata: {json.dumps(result)}\n\n"
        else:
            # Stream the response text token by token
            response_text = result.get("response", "")
            words = response_text.split(" ")
            for word in words:
                yield f"event: token\ndata: {json.dumps({'text': word + ' '})}\n\n"
            yield f"event: done\ndata: {json.dumps({'engine': 'agent', 'type': 'agent_response'})}\n\n"

    except Exception as e:
        logger.exception("Agent SSE error")
        try:
            from app.rag.pipeline import rag_stream
            token_gen, _ = rag_stream(query=req.message, chat_history=req.chat_history)
            for token in token_gen:
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            yield f"event: done\ndata: {json.dumps({'engine': 'rag'})}\n\n"
        except Exception:
            fallback_text = "I'm sorry, I couldn't retrieve those details. Please specify the property ID or try again."
            yield f"event: token\ndata: {json.dumps({'text': fallback_text})}\n\n"
            yield f"event: done\ndata: {json.dumps({'engine': 'error'})}\n\n"


@router.post("/confirm")
async def confirm_action(req: ConfirmRequest):
    """
    Handle user confirmation or cancellation of a pending agent action.
    """
    from app.agent.graph import AgentState, handle_confirmed_node, handle_cancelled_node
    from langchain_core.messages import HumanMessage

    pending = req.pending_confirmation
    if not pending:
        raise HTTPException(status_code=400, detail="No pending confirmation provided.")

    user_memory = get_user_memory(req.user_identifier)
    state: AgentState = {
        "messages": [HumanMessage(content=req.decision)],
        "user_memory": user_memory,
        "user_identifier": req.user_identifier,
        "pending_confirmation": pending,
        "confirmation_result": None,
        "final_response": None,
    }

    if req.decision.lower() in ("confirmed", "yes", "confirm", "book it", "send it", "ok", "okay"):
        result_state = handle_confirmed_node(state)
        return {
            "status": "confirmed",
            "message": _last_message_content(result_state) or "Action confirmed and executed successfully.",
        }
    else:
        result_state = handle_cancelled_node(state)
        return {
            "status": "cancelled",
            "message": result_state.get("final_response") or "Action cancelled.",
        }


def _last_message_content(state: dict) -> str | None:
    messages = state.get("messages") or []
    if not messages:
        return None
    return getattr(messages[-1], "content", None)
