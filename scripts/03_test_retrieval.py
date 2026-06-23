# scripts/03_test_retrieval.py
"""
Phase 1A - RETRIEVAL SANITY CHECK
===================================
Runs test queries against the ChromaDB vector store to confirm that
the embedding pipeline produced semantically useful results.

Run after 02_embed_and_store.py:
    python scripts/03_test_retrieval.py

Phase 1A exit criterion: at least 1 case returned for each of 3 queries
with similarity scores > 0. If this script exits with code 0, Phase 1B
may begin.

Course concept: Deployability (Day 5) - setup can be verified end-to-end.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import chromadb
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY         = os.getenv("JINA_API_KEY")
JINA_EMBEDDING_MODEL = "jina-embeddings-v3"
CHROMA_DB_PATH       = os.getenv("CHROMA_DB_PATH", "./db")
COLLECTION_NAME      = "surgery_cases"
TOP_K               = 3

if not JINA_API_KEY:
    print("ERROR: JINA_API_KEY not set. Copy .env.example to .env and fill in the key.")
    sys.exit(1)


def embed_query(text):
    """Embed a single query string using the retrieval.query task adapter."""
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
    return response.json()["data"][0]["embedding"]


def search(collection, query, top_k=TOP_K):
    """Embed query and retrieve top_k matching cases from ChromaDB."""
    print(f"\n{'=' * 60}")
    print(f"QUERY: {query}")
    print("=" * 60)

    vec = embed_query(query)
    results = collection.query(
        query_embeddings=[vec],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = list(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ))

    if not hits:
        print("  NO RESULTS - vector store may be empty")
        return 0

    for i, (doc, meta, dist) in enumerate(hits):
        sim = round(1 - dist, 3)
        print(f"\n  Result {i + 1}  (similarity: {sim})")
        print(f"    Case ID   : {meta.get('case_id')}")
        print(f"    Diagnosis : {meta.get('diagnosis')}")
        print(f"    Disease   : {meta.get('disease')}")
        print(f"    Age / Sex : {meta.get('age')}y / {meta.get('sex')}")
        print(f"    Has CT    : {meta.get('has_ct')}  |  Has US: {meta.get('has_us')}")
        print(f"    Preview   : {doc[:200]}...")

    return len(hits)


def main():
    print("=" * 60)
    print("SurgMentor - Phase 1A: Retrieval Sanity Check")
    print("=" * 60)
    print(f"\nChromaDB path : {CHROMA_DB_PATH}")
    print(f"Collection    : {COLLECTION_NAME}")

    chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma.get_collection(COLLECTION_NAME)

    total_cases = collection.count()
    print(f"Cases in store: {total_cases}")

    if total_cases == 0:
        print("\nERROR: Vector store is empty. Run scripts/02_embed_and_store.py first.")
        sys.exit(1)

    # Phase 1A exit criterion: 3 queries must each return >= 1 result
    test_queries = [
        "young patient with right lower quadrant pain and fever",
        "gallbladder stones ultrasound jaundice",
        "bowel obstruction vomiting CT scan findings",
    ]

    all_passed = True
    for query in test_queries:
        hits = search(collection, query)
        if hits == 0:
            print(f"\nFAIL: Query returned 0 results: '{query}'")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("Phase 1A exit criterion: PASSED")
        print(f"  All {len(test_queries)} queries returned >= 1 result with similarity scores.")
        print("  Phase 1B (Tool Layer) may now begin.")
    else:
        print("Phase 1A exit criterion: FAILED")
        print("  One or more queries returned no results.")
        print("  Re-run scripts/02_embed_and_store.py and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
