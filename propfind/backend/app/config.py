"""
config.py — Centralized configuration from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load .env from backend directory
_backend_dir = Path(__file__).resolve().parents[1]
_env_path = _backend_dir / ".env"
load_dotenv(dotenv_path=_env_path)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

GROQ_AGENT_MODEL: str = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b")
GROQ_FAST_MODEL: str = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

def _resolve_path(value: str | None, default: Path) -> Path:
    """Resolve relative .env paths from the backend directory, not process cwd."""
    if not value:
        return default.resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _backend_dir / path
    return path.resolve()


def _resolve_sqlite_url(value: str | None, default_file: Path) -> str:
    if not value:
        return f"sqlite:///{default_file.resolve()}"
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        return value
    raw_path = value[len(prefix):]
    if raw_path in {":memory:", ""}:
        return value
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = _backend_dir / path
    return f"sqlite:///{path.resolve()}"


DATASET_PATH: Path = _resolve_path(
    os.getenv("DATASET_PATH"),
    _backend_dir / "../../Dataset",
)

DATABASE_URL: str = _resolve_sqlite_url(
    os.getenv("DATABASE_URL"),
    _backend_dir / "data" / "propfind.db",
)
CHROMA_PATH: str = str(_resolve_path(os.getenv("CHROMA_PATH"), _backend_dir / "data" / "chroma"))
REPORTS_PATH: str = str(_resolve_path(os.getenv("REPORTS_PATH"), _backend_dir / "reports"))

# Ensure output directories exist
Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
Path(REPORTS_PATH).mkdir(parents=True, exist_ok=True)

# Groq client singleton — initialised lazily to avoid crashing on import if key is missing
_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client
