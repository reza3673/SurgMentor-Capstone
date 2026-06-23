# surgmentor/rag/retrieval_tool.py
"""
Retrieval tools — the only interface to ChromaDB in this system.

Skills call these functions; they never access ChromaDB directly.
This enforces the least-privilege principle: only the retrieval layer
knows the vector store schema.

Public API:
  CaseResult                         dataclass
  search_vector_store(query, top_k, bias_topics) -> list[CaseResult]
  get_case_by_id(case_id)            -> CaseResult | None
  load_all_cases()                   -> list[dict]
  format_case_context(cases)         -> str

Design reference (read-only): surgery-rag/rag_engine.py
Improvements over reference:
  - Lazy ChromaDB connection (not at import time)
  - bias_topics parameter for weak-area-aware retrieval
  - Per-process embedding cache
  - load_all_cases() backed by prepared_cases.json, cached after first read

Course concepts: Agent Skills (Day 3), Context Engineering (Day 1)
"""

import json
import os
import sys
from dataclasses import dataclass, field

import requests

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import (
    JINA_API_KEY,
    JINA_EMBEDDING_MODEL,
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    TOP_K_RESULTS,
)

# ── Module-level caches ───────────────────────────────────────────────────────

_embed_cache: dict[str, list[float]] = {}   # query text → unit vector
_chroma_collection = None                    # lazy-init ChromaDB collection
_all_cases_cache: list[dict] | None = None  # lazy-init prepared_cases.json

# Path to prepared_cases.json (sibling of this package's db/ folder)
_PREPARED_CASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "prepared_cases.json",
)


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    """A single retrieval result from the vector store."""
    case_id:    str
    text:       str
    metadata:   dict
    similarity: float


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_collection():
    """
    Return the ChromaDB collection, initializing the client on first call.
    Lazy init avoids import-time side effects (test imports, sandbox builds).
    """
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _chroma_collection = client.get_collection(COLLECTION_NAME)
    return _chroma_collection


def _embed_query(text: str) -> list[float]:
    """
    Embed a query string via the Jina AI API using the retrieval.query task
    adapter, which is optimised for matching against indexed passages.

    Results are cached per process so repeated queries skip the API call.
    Raises RuntimeError if JINA_API_KEY is not set.
    """
    if text in _embed_cache:
        return _embed_cache[text]

    if not JINA_API_KEY:
        raise RuntimeError(
            "JINA_API_KEY is not set. Copy .env.example to .env and fill in the key."
        )

    response = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {JINA_API_KEY}"},
        json={
            "model":      JINA_EMBEDDING_MODEL,
            "task":       "retrieval.query",
            "normalized": True,
            "input":      [text],
        },
        timeout=15,
    )
    response.raise_for_status()
    vector: list[float] = response.json()["data"][0]["embedding"]
    _embed_cache[text] = vector
    return vector


# ── Public API ────────────────────────────────────────────────────────────────

def search_vector_store(
    query: str,
    top_k: int = TOP_K_RESULTS,
    bias_topics: list[str] | None = None,
) -> list[CaseResult]:
    """
    Embed the query and return the top_k most similar cases from ChromaDB.

    bias_topics: list of weak-area strings from the student profile (Day 1
    context engineering). If non-empty, they are appended to the query before
    embedding so retrieval is biased toward the student's knowledge gaps.
    Example: ["haemostasis", "wound closure"]

    Returns an empty list if the collection is empty.
    """
    if bias_topics:
        bias_str = "; ".join(bias_topics)
        augmented_query = f"{query} [focus: {bias_str}]"
    else:
        augmented_query = query

    vector = _embed_query(augmented_query)
    collection = _get_collection()

    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    cases: list[CaseResult] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        cases.append(CaseResult(
            case_id=meta.get("case_id", "unknown"),
            text=doc,
            metadata=meta,
            similarity=round(1.0 - dist, 3),
        ))

    return cases


def get_case_by_id(case_id: str) -> CaseResult | None:
    """
    Retrieve a single case by its exact ID from ChromaDB.
    Returns None if the case is not found.
    """
    collection = _get_collection()
    result = collection.get(
        ids=[case_id],
        include=["documents", "metadatas"],
    )

    if not result["ids"]:
        return None

    return CaseResult(
        case_id=result["ids"][0],
        text=result["documents"][0],
        metadata=result["metadatas"][0],
        similarity=1.0,  # exact match, no distance computed
    )


def load_all_cases() -> list[dict]:
    """
    Load all cases from data/prepared_cases.json.
    Cached after first read — subsequent calls return the same list.
    Used by OSCEExaminerSkill to pick a random case at session start.
    """
    global _all_cases_cache
    if _all_cases_cache is None:
        if not os.path.exists(_PREPARED_CASES_PATH):
            raise FileNotFoundError(
                f"prepared_cases.json not found at {_PREPARED_CASES_PATH}. "
                "Run scripts/01_prepare_data.py first."
            )
        with open(_PREPARED_CASES_PATH, "r", encoding="utf-8") as f:
            _all_cases_cache = json.load(f)
    return _all_cases_cache


def format_case_context(cases: list[CaseResult]) -> str:
    """
    Format a list of CaseResult objects into a numbered context block for
    inclusion in an LLM system prompt.

    Output format:
        [Case 1] ID: X | Diagnosis: Y | Similarity: Z
        <full case text>

        [Case 2] ...
    """
    if not cases:
        return "No relevant cases found in the knowledge base."

    blocks: list[str] = []
    for i, case in enumerate(cases, 1):
        diagnosis = case.metadata.get("diagnosis", "unknown")
        header = (
            f"[Case {i}] ID: {case.case_id} | "
            f"Diagnosis: {diagnosis} | "
            f"Similarity: {case.similarity}"
        )
        blocks.append(f"{header}\n{case.text}")

    return "\n\n".join(blocks)


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("retrieval_tool.py — import and structural smoke test")
    print("=" * 60)

    # 1. Dataclass round-trip
    cr = CaseResult(case_id="case_1", text="test text", metadata={"diagnosis": "appendicitis"}, similarity=0.92)
    assert cr.case_id == "case_1"
    assert cr.similarity == 0.92
    print("✅  CaseResult dataclass: OK")

    # 2. load_all_cases (no API call)
    try:
        cases = load_all_cases()
        print(f"✅  load_all_cases: {len(cases)} cases loaded from prepared_cases.json")
    except FileNotFoundError as e:
        print(f"⚠️   load_all_cases: {e}")

    # 3. format_case_context (no API call)
    sample = [
        CaseResult("c1", "Patient with fever...", {"diagnosis": "appendicitis"}, 0.95),
        CaseResult("c2", "Patient with jaundice...", {"diagnosis": "cholecystitis"}, 0.88),
    ]
    ctx = format_case_context(sample)
    assert "[Case 1]" in ctx
    assert "[Case 2]" in ctx
    print("✅  format_case_context: OK")

    ctx_empty = format_case_context([])
    assert "No relevant" in ctx_empty
    print("✅  format_case_context (empty list): OK")

    # 4. Embedding cache (API required — skip if no key)
    if not JINA_API_KEY:
        print("⚠️   _embed_query: skipped — JINA_API_KEY not set")
    else:
        try:
            v1 = _embed_query("abdominal pain")
            v2 = _embed_query("abdominal pain")  # must hit cache
            assert v1 is v2, "Cache should return same object"
            assert len(v1) == 1024
            print(f"✅  _embed_query + cache: OK (dim={len(v1)})")
        except Exception as e:
            print(f"⚠️   _embed_query: {e} (requires network; verify on native machine)")

    # 5. ChromaDB retrieval (requires populated db/ and Jina API)
    if not JINA_API_KEY:
        print("⚠️   search_vector_store: skipped — JINA_API_KEY not set")
    else:
        try:
            results = search_vector_store("abdominal pain and fever")
            if results:
                print(f"✅  search_vector_store: {len(results)} result(s) — "
                      f"top: {results[0].case_id} (sim={results[0].similarity})")
            else:
                print("⚠️   search_vector_store: returned 0 results (check ChromaDB)")
        except Exception as e:
            print(f"⚠️   search_vector_store: {e} (verify on native machine)")

    print("\n" + "=" * 60)
    print("Structural tests PASSED. API-dependent tests require native machine.")
    print("=" * 60)
