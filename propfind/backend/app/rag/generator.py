"""
generator.py — Groq-powered answer generation with strict grounding.
Supports both streaming (SSE) and non-streaming modes.
"""
from __future__ import annotations

import logging
from typing import Generator, Sequence

from app.config import get_groq_client, GROQ_AGENT_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PropFind AI, a helpful real estate assistant specialising in Delhi NCR properties.

RULES:
1. Answer ONLY from the provided property context. Do not hallucinate prices, localities, or amenity lists.
2. If the context is empty or irrelevant, say exactly: "I couldn't find any properties matching that in our current listings."
3. Format prices in ₹ with Indian number formatting (lakhs/crores where appropriate).
4. Be concise, friendly, and professional.
5. When listing properties in response to a search, ALWAYS format them as a numbered list and include the Property ID in bold for each property, e.g.:
   1. **[PROP1001]** 2 BHK Independent House in Gurgaon Sector 56 — ₹2.51 crores, 1,232 sq.ft.
6. When the user asks for owner or contact details (e.g. "Give owner details of 1" or "Who owns PROP1001?"), ALWAYS extract and provide the owner's full name, phone number, and email address clearly from the context.
7. If the user refers to a property by item number (e.g., "1", "#1", "first property"), match it to Item #1 from the context or recent conversation history and answer accurately.
"""


def _build_context_str(chunks: Sequence[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        pid = chunk.get("property_id") or f"PROP{1000+i}"
        parts.append(f"[Item #{i} - Property ID: {pid}]\n{chunk['text']}")
    return "\n\n".join(parts)


def generate_answer(
    query: str,
    chunks: Sequence[dict],
    chat_history: list[dict] | None = None,
) -> str:
    """Non-streaming generation. Returns the full answer string."""
    client = get_groq_client()
    context_str = _build_context_str(chunks)

    user_content = f"""Context (retrieved listings):
{context_str}

User question: {query}"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-6:])  # last 3 turns
    messages.append({"role": "user", "content": user_content})

    resp = client.chat.completions.create(
        model=GROQ_AGENT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )
    return resp.choices[0].message.content


def stream_answer(
    query: str,
    chunks: Sequence[dict],
    chat_history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """Streaming generation. Yields text delta strings."""
    client = get_groq_client()
    context_str = _build_context_str(chunks)

    user_content = f"""Context (retrieved listings):
{context_str}

User question: {query}"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": user_content})

    stream = client.chat.completions.create(
        model=GROQ_AGENT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
