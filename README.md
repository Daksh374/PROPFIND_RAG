# PropFind — AI Real Estate Assistant for Delhi NCR

> **Full-stack RAG + Agentic AI system** using Groq LLMs, LangGraph, ChromaDB, FastAPI, and React.

---

## 🚀 Quick Start

### 1. Backend Setup

```bash
cd propfind/backend

# Copy and fill in your Groq API key
cp .env.example .env
# Edit .env: set GROQ_API_KEY=<your_key_from_console.groq.com>

# Create virtual environment & install
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Ingest data (first time only — downloads ~90MB embedding model)
python scripts/ingest.py

# Start backend
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd propfind/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# → Opens at http://localhost:5173
```

---

## 🏗 Architecture

```
propfind/
├── backend/
│   ├── app/
│   │   ├── config.py              # Env vars, Groq client singleton
│   │   ├── database.py            # SQLAlchemy models (9 tables)
│   │   ├── ingest/
│   │   │   ├── loader.py          # CSV → SQLite (adapter layer)
│   │   │   ├── chunker.py         # NL chunks (property + locality)
│   │   │   └── embedder.py        # ChromaDB upsert + query
│   │   ├── rag/
│   │   │   ├── retriever.py       # SQL pre-filter → vector search
│   │   │   ├── generator.py       # Groq answer generation (streaming)
│   │   │   └── pipeline.py        # RAG orchestrator
│   │   ├── agent/
│   │   │   ├── tools.py           # 7 LangGraph tools
│   │   │   ├── graph.py           # LangGraph state machine
│   │   │   ├── memory.py          # User preference CRUD
│   │   │   └── prompts.py         # System prompts
│   │   ├── pdf/
│   │   │   └── report.py          # ReportLab PDF generator
│   │   └── routers/
│   │       ├── chat.py            # POST /chat (SSE) + POST /chat/confirm
│   │       ├── properties.py      # GET /properties (paginated + filtered)
│   │       ├── agent.py           # Agent action endpoints
│   │       └── reports.py         # PDF download
│   ├── scripts/
│   │   ├── ingest.py              # One-shot data ingestion
│   │   └── test_rag.py            # RAG verification (20 queries)
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx                # 3-panel layout
        └── components/
            ├── ChatPanel.jsx      # SSE streaming chat
            ├── MessageBubble.jsx  # RAG / agent / confirmation messages
            ├── ConfirmationCard.jsx # Human-in-the-loop confirm UI
            ├── FilterSidebar.jsx  # Property filters
            ├── PropertyCard.jsx   # Card w/ compare toggle
            ├── ComparisonView.jsx # Side-by-side + PDF download
            └── VisitsTab.jsx      # Visit/inquiry status tracking
```

---

## 🔧 Agent Tools

| Tool | Description | Confirmation Required |
|---|---|---|
| `search_properties` | Semantic + filtered property search | No |
| `get_property_details` | Full property + owner info | No |
| `estimate_fair_price` | Market-rate estimation from sales data | No |
| `compare_properties` | Side-by-side comparison with market rating | No |
| `schedule_visit` | Create a property visit | **Yes** |
| `send_owner_inquiry` | Message a property owner | **Yes** |
| `generate_comparison_report` | Download PDF comparison report | No |

---

## 📋 Key Design Decisions

See [DECISIONS.md](./DECISIONS.md) for full rationale.

---

## 🧪 Running Tests

```bash
# From propfind/backend/ with venv activated
python scripts/test_rag.py
```

---

## 🌐 API Docs

After starting the backend: **http://localhost:8000/docs**

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector DB | ChromaDB (persistent) |
| Agent | LangGraph + LangChain-Groq |
| Database | SQLite (SQLAlchemy) |
| Backend | FastAPI + SSE |
| Frontend | React + Vite + Tailwind CSS v3 |

