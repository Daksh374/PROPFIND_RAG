"""
main.py — FastAPI application entrypoint.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import chat, properties, agent, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB tables."""
    logger.info("Initialising database...")
    init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down PropFind API.")


app = FastAPI(
    title="PropFind API",
    description="Real Estate RAG + Agentic AI for Delhi NCR",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(properties.router)
app.include_router(agent.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "PropFind API"}


@app.get("/")
def root():
    return {
        "service": "PropFind RAG + Agent API",
        "docs": "/docs",
        "health": "/health",
    }
