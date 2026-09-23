"""
graph.py — LangGraph state machine for the PropFind agent.

Flow:
  user_input → plan → tool_call → confirm_gate → [await_confirmation | execute] → respond

The confirm_gate enforces human-in-the-loop for schedule_visit and send_owner_inquiry,
regardless of how the user phrases their request (adversarial-resistant).
"""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Literal

from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage
)
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.agent.prompts import build_system_prompt
from app.agent.tools import ALL_TOOLS, CONFIRMATION_REQUIRED_TOOLS
from app.config import GROQ_API_KEY, GROQ_AGENT_MODEL

logger = logging.getLogger(__name__)


# ─── State definition ─────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_memory: dict
    user_identifier: str
    pending_confirmation: dict | None   # Holds confirmation payload while waiting
    confirmation_result: str | None     # "confirmed" | "cancelled"
    final_response: str | None


# ─── Nodes ───────────────────────────────────────────────────────────────────

def _get_llm_with_tools(model_name: str = GROQ_AGENT_MODEL):
    from app.config import GROQ_FAST_MODEL
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model=model_name,
            temperature=0.2,
            max_tokens=2048,
            model_kwargs={"reasoning_effort": "low"},
        )
        return llm.bind_tools(ALL_TOOLS)
    except Exception:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model=GROQ_FAST_MODEL,
            temperature=0.2,
            max_tokens=2048,
            model_kwargs={"reasoning_effort": "low"},
        )
        return llm.bind_tools(ALL_TOOLS)


def plan_node(state: AgentState) -> dict:
    """Call LLM with tools to decide next action."""
    from app.config import GROQ_FAST_MODEL
    system_prompt = build_system_prompt(state.get("user_memory", {}))
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    try:
        llm = _get_llm_with_tools(GROQ_AGENT_MODEL)
        response = llm.invoke(messages)
        return {"messages": [response]}
    except Exception as e:
        logger.warning(f"Primary model failed in plan_node ({e}), trying fast model...")
        try:
            llm_fast = _get_llm_with_tools(GROQ_FAST_MODEL)
            response = llm_fast.invoke(messages)
            return {"messages": [response]}
        except Exception as e2:
            logger.warning(f"Fast model also failed in plan_node: {e2}. Executing RAG fallback.")
            last_user_msg = ""
            for m in reversed(state["messages"]):
                if isinstance(m, HumanMessage):
                    last_user_msg = getattr(m, "content", "")
                    break

            from app.rag.pipeline import rag_query
            history = []
            for m in state["messages"][:-1]:
                role = "assistant" if isinstance(m, AIMessage) else "user"
                content = getattr(m, "content", "")
                if content:
                    history.append({"role": role, "content": content})

            rag_res = rag_query(query=last_user_msg or "property details", chat_history=history)
            answer = rag_res.get("answer") or "I couldn't retrieve the property details right now. Please try asking again."
            return {"messages": [AIMessage(content=answer)]}


def confirm_gate_node(state: AgentState) -> dict:
    """
    Check if the last AI message has tool calls that require confirmation.
    If so, extract and store the confirmation payload — do NOT execute yet.
    This node is adversarial-resistant: it checks tool name, not LLM intent.
    """
    last_msg = state["messages"][-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {"pending_confirmation": None}

    for tc in last_msg.tool_calls:
        if tc["name"] in CONFIRMATION_REQUIRED_TOOLS:
            logger.info(f"Confirmation gate triggered for tool: {tc['name']}")
            return {
                "pending_confirmation": {
                    "tool_name": tc["name"],
                    "tool_call_id": tc["id"],
                    "args": tc["args"],
                    "message": _confirmation_message(tc["name"], tc["args"]),
                }
            }

    return {"pending_confirmation": None}


def execute_tools_node(state: AgentState) -> dict:
    """Execute all tool calls in the last AI message."""
    from langchain_core.messages import ToolMessage as LCToolMessage

    last_msg = state["messages"][-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {}

    tool_map = {t.name: t for t in ALL_TOOLS}
    tool_messages = []

    for tc in last_msg.tool_calls:
        tool_fn = tool_map.get(tc["name"])
        if not tool_fn:
            tool_messages.append(
                LCToolMessage(
                    content=f"Tool {tc['name']} not found.",
                    tool_call_id=tc["id"],
                )
            )
            continue
        try:
            result = tool_fn.invoke(tc["args"])
            tool_messages.append(
                LCToolMessage(content=str(result), tool_call_id=tc["id"])
            )
        except Exception as e:
            logger.exception(f"Tool {tc['name']} failed")
            tool_messages.append(
                LCToolMessage(content=f"Error: {e}", tool_call_id=tc["id"])
            )

    return {"messages": tool_messages}


def respond_node(state: AgentState) -> dict:
    """Final LLM call to synthesize tool results into a human response."""
    from app.config import GROQ_FAST_MODEL
    system_prompt = build_system_prompt(state.get("user_memory", {}))
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model=GROQ_AGENT_MODEL,
            temperature=0.3,
            max_tokens=1024,
            model_kwargs={"reasoning_effort": "low"},
        )
        response = llm.invoke(messages)
    except Exception as e:
        logger.warning(f"Primary model failed in respond_node ({e}), trying fast model...")
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model=GROQ_FAST_MODEL,
            temperature=0.3,
            max_tokens=1024,
            model_kwargs={"reasoning_effort": "low"},
        )
        response = llm.invoke(messages)

    return {
        "messages": [response],
        "final_response": response.content,
    }


def await_confirmation_node(state: AgentState) -> dict:
    """
    Placeholder node — the graph pauses here waiting for external confirmation.
    The actual response is injected by the /chat/confirm endpoint.
    """
    pending = state.get("pending_confirmation", {})
    msg = pending.get("message") if pending else "Please confirm the action."
    return {
        "final_response": json.dumps({
            "type": "confirmation_required",
            "pending": pending,
            "message": msg,
        })
    }


def handle_confirmed_node(state: AgentState) -> dict:
    """Execute the pending tool after user confirmation."""
    from langchain_core.messages import ToolMessage as LCToolMessage

    pending = state.get("pending_confirmation")
    if not pending:
        return {}

    try:
        result = _finalize_confirmed_action(pending)
    except Exception as e:
        result = f"Error executing confirmed action: {e}"

    tool_msg = LCToolMessage(
        content=str(result),
        tool_call_id=pending.get("tool_call_id", "confirmed"),
    )
    return {
        "messages": [tool_msg],
        "pending_confirmation": None,
        "confirmation_result": "confirmed",
    }


def handle_cancelled_node(state: AgentState) -> dict:
    """User cancelled the pending action."""
    pending = state.get("pending_confirmation", {})
    tool_name = pending.get("tool_name", "action") if pending else "action"
    _cancel_pending_record(pending)
    return {
        "messages": [
            AIMessage(content=f"Understood, the {tool_name} has been cancelled.")
        ],
        "pending_confirmation": None,
        "confirmation_result": "cancelled",
        "final_response": f"The {tool_name} has been cancelled as requested.",
    }


def _confirmation_message(tool_name: str, args: dict) -> str:
    """Build a user-facing confirmation summary without mutating the DB."""
    from app.database import Property, SessionLocal

    property_id = args.get("property_id", "")
    title = property_id
    locality = ""
    with SessionLocal() as session:
        prop = session.query(Property).filter(Property.property_id == property_id).first()
        if prop:
            title = prop.title
            locality = f" in {prop.locality}" if prop.locality else ""

    if tool_name == "schedule_visit":
        return (
            f"Please confirm the visit for **{title}**{locality} "
            f"on {args.get('scheduled_datetime', 'the selected time')}."
        )
    if tool_name == "send_owner_inquiry":
        preview = (args.get("message") or "").strip()
        if len(preview) > 140:
            preview = preview[:137] + "..."
        return f"Please confirm sending this inquiry for **{title}**{locality}: \"{preview}\""
    return "Please confirm this action."


def _finalize_confirmed_action(pending: dict) -> str:
    """Create or update the confirmed Visit/Inquiry exactly once."""
    from app.database import Visit, Inquiry, Property, SessionLocal

    tool_name = pending.get("tool_name")
    args = pending.get("args", {})
    with SessionLocal() as session:
        if tool_name == "schedule_visit":
            prop = session.query(Property).filter(Property.property_id == args.get("property_id")).first()
            if not prop:
                return json.dumps({"error": f"Property {args.get('property_id')} not found."})

            visit = (
                session.query(Visit)
                .filter(
                    Visit.property_id == args.get("property_id"),
                    Visit.status == "pending_confirmation",
                )
                .order_by(Visit.created_at.desc())
                .first()
            )
            if visit:
                if args.get("user_name"):
                    visit.user_name = args["user_name"]
                if args.get("user_email"):
                    visit.user_email = args["user_email"]
                if args.get("scheduled_datetime"):
                    visit.scheduled_datetime = args["scheduled_datetime"]
                if args.get("notes") is not None:
                    visit.notes = args["notes"]
                visit.status = "scheduled"
                session.commit()
                session.refresh(visit)
            else:
                visit = Visit(
                    property_id=args.get("property_id", ""),
                    user_name=args.get("user_name", "User"),
                    user_email=args.get("user_email", "user@example.com"),
                    scheduled_datetime=args.get("scheduled_datetime", ""),
                    notes=args.get("notes"),
                    status="scheduled",
                )
                session.add(visit)
                session.commit()
                session.refresh(visit)

            return json.dumps({
                "action": "schedule_visit",
                "visit_id": visit.id,
                "property_id": visit.property_id,
                "status": visit.status,
                "message": f"Visit scheduled for {prop.title} on {visit.scheduled_datetime}.",
            }, ensure_ascii=False)

        elif tool_name == "send_owner_inquiry":
            prop = session.query(Property).filter(Property.property_id == args.get("property_id")).first()
            if not prop:
                return json.dumps({"error": f"Property {args.get('property_id')} not found."})

            inquiry = (
                session.query(Inquiry)
                .filter(
                    Inquiry.property_id == args.get("property_id"),
                    Inquiry.status == "pending_confirmation",
                )
                .order_by(Inquiry.created_at.desc())
                .first()
            )
            if inquiry:
                if args.get("user_name"):
                    inquiry.user_name = args["user_name"]
                if args.get("message"):
                    inquiry.message = args["message"]
                inquiry.status = "sent"
                session.commit()
                session.refresh(inquiry)
            else:
                inquiry = Inquiry(
                    property_id=args.get("property_id", ""),
                    owner_id=prop.owner_id,
                    message=args.get("message", ""),
                    user_name=args.get("user_name", "User"),
                    status="sent",
                )
                session.add(inquiry)
                session.commit()
                session.refresh(inquiry)

            return json.dumps({
                "action": "send_owner_inquiry",
                "inquiry_id": inquiry.id,
                "property_id": inquiry.property_id,
                "status": inquiry.status,
                "message": f"Inquiry sent for {prop.title}.",
            }, ensure_ascii=False)

    return json.dumps({"error": f"Unsupported action: {tool_name}"})


def _cancel_pending_record(pending: dict | None) -> None:
    """Mark any matching pre-created pending row as cancelled."""
    if not pending:
        return
    from app.database import Visit, Inquiry, SessionLocal

    tool_name = pending.get("tool_name")
    args = pending.get("args", {})
    model = Visit if tool_name == "schedule_visit" else Inquiry if tool_name == "send_owner_inquiry" else None
    if model is None:
        return

    with SessionLocal() as session:
        row = (
            session.query(model)
            .filter(
                model.property_id == args.get("property_id"),
                model.status == "pending_confirmation",
            )
            .order_by(model.created_at.desc())
            .first()
        )
        if row:
            row.status = "cancelled"
            session.commit()


def _coerce_history_messages(chat_history: list | None) -> list:
    """Convert frontend {role, content} history into LangChain message objects."""
    messages = []
    for item in (chat_history or [])[-6:]:
        if isinstance(item, (HumanMessage, AIMessage)):
            messages.append(item)
            continue
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not content:
            continue
        if item.get("role") == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


# ─── Routing ──────────────────────────────────────────────────────────────────

def route_after_plan(state: AgentState) -> Literal["confirm_gate", "respond"]:
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "confirm_gate"
    return "respond"


def route_after_confirm_gate(
    state: AgentState,
) -> Literal["await_confirmation", "execute_tools"]:
    if state.get("pending_confirmation"):
        return "await_confirmation"
    return "execute_tools"


# ─── Graph construction ───────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("plan", plan_node)
    g.add_node("confirm_gate", confirm_gate_node)
    g.add_node("execute_tools", execute_tools_node)
    g.add_node("await_confirmation", await_confirmation_node)
    g.add_node("respond", respond_node)

    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route_after_plan)
    g.add_conditional_edges("confirm_gate", route_after_confirm_gate)
    g.add_edge("execute_tools", "respond")
    g.add_edge("await_confirmation", END)
    g.add_edge("respond", END)

    return g.compile()


# Compile once at module load
agent_graph = build_graph()


def run_agent(
    user_message: str,
    user_identifier: str = "anonymous",
    user_memory: dict | None = None,
    chat_history: list | None = None,
) -> dict:
    """
    Run the agent graph for a single user turn.
    Returns {"response": str, "pending_confirmation": dict | None, "type": str}
    """
    messages = _coerce_history_messages(chat_history)
    messages.append(HumanMessage(content=user_message))

    initial_state: AgentState = {
        "messages": messages,
        "user_memory": user_memory or {},
        "user_identifier": user_identifier,
        "pending_confirmation": None,
        "confirmation_result": None,
        "final_response": None,
    }

    final_state = agent_graph.invoke(initial_state)

    pending = final_state.get("pending_confirmation")
    final = final_state.get("final_response") or ""

    if pending:
        # Try to parse confirmation message from tool result
        try:
            tool_result = json.loads(final)
            msg = tool_result.get("message", "Please confirm the action.")
        except Exception:
            msg = final
        return {
            "type": "confirmation_required",
            "response": msg,
            "pending_confirmation": pending,
        }

    return {
        "type": "agent_response",
        "response": final,
        "pending_confirmation": None,
    }
