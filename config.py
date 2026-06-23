# config.py
"""
SurgMentor configuration — all constants loaded from environment variables.

Copy .env.example to .env and fill in real values before running.
Never commit .env to version control.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API KEYS ──────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
JINA_API_KEY     = os.getenv("JINA_API_KEY")

# ── DEEPSEEK LLM ──────────────────────────────────────────────────────────────
DEEPSEEK_CHAT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL   = "https://api.deepseek.com"

# ── JINA EMBEDDINGS ───────────────────────────────────────────────────────────
JINA_EMBEDDING_MODEL      = "jina-embeddings-v3"
JINA_EMBEDDING_DIMENSIONS = 1024
EMBEDDING_BATCH_SIZE      = 32

# ── VECTOR DATABASE ───────────────────────────────────────────────────────────
CHROMA_DB_PATH  = os.getenv("CHROMA_DB_PATH", "./db")   # override via env for non-standard layouts
COLLECTION_NAME = "surgery_cases"
TOP_K_RESULTS   = 3

# ── SESSION MEMORY ────────────────────────────────────────────────────────────
AGENT_SESSION_DB_PATH = os.getenv("AGENT_SESSION_DB_PATH", "./data/surgmentor_agent.db")
HISTORY_WINDOW        = 10   # max conversation turns kept in context for chat mode

# ── SECURITY ──────────────────────────────────────────────────────────────────
MAX_INPUT_LENGTH             = 2000   # characters; inputs longer than this are rejected
SCOPE_CLASSIFICATION_ENABLED = os.getenv("SCOPE_CLASSIFICATION_ENABLED", "true").lower() == "true"

# ── EVALUATION ────────────────────────────────────────────────────────────────
EVAL_LOG_PATH    = "./eval_log.jsonl"
MIN_OSCE_TURNS   = 3         # minimum student turns before a session can be scored

# ── GRADIO INTERFACE ──────────────────────────────────────────────────────────
GRADIO_PORT      = int(os.getenv("GRADIO_PORT", "7860"))

# ── FASTAPI / CUSTOM FRONTEND ─────────────────────────────────────────────────
FASTAPI_PORT     = int(os.getenv("FASTAPI_PORT", "8000"))

# ── MCP SERVER (stretch goal) ─────────────────────────────────────────────────
USE_MCP          = os.getenv("USE_MCP", "false").lower() == "true"
MCP_SERVER_PORT  = int(os.getenv("MCP_SERVER_PORT", "8765"))
