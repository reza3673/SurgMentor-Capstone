# scripts/02_embed_and_store.py
"""
Phase 1A - EMBEDDING PIPELINE + VECTOR DATABASE
Reads data/prepared_cases.json, embeds each case via the Jina AI API,
and stores vectors in ChromaDB at db/.

Run:
    python scripts/02_embed_and_store.py

Safe to re-run: deletes and recreates the ChromaDB collection on each run.

Build-environment note: set CHROMA_BUILD_PATH env var when the target path
cannot accept SQLite writes (e.g. mounted Windows volume from Linux sandbox).
On native Windows/macOS, leave unset - ChromaDB writes directly to ./db.

Course concept: Deployability (Day 5) - reproducible setup in two commands.
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import chromadb
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY         = os.getenv("JINA_API_KEY")
JINA_EMBEDDING_MODEL = "jina-embeddings-v3"
CHROMA_DB_PATH       = "./db"
COLLECTION_NAME      = "surgery_cases"
EMBEDDING_BATCH_SIZE = 32
PREPARED_CASES_FILE  = "./data/prepared_cases.json"

# Build-environment override: lets the script write ChromaDB to a local
# temp path when the target mount does not support SQLite file locking.
CHROMA_BUILD_PATH = os.getenv("CHROMA_BUILD_PATH", CHROMA_DB_PATH)

if not JINA_API_KEY:
    raise EnvironmentError(
        "JINA_API_KEY not found in environment.\n"
        "Copy .env.example to .env and fill in your Jina AI API key."
    )


def get_embeddings(texts, task="retrieval.passage"):
    """
    Embed texts via the Jina AI API.
    task='retrieval.passage' for indexed documents.
    task='retrieval.query'   for query strings at retrieval time.
    normalized=True produces unit vectors - cosine similarity = dot product.
    """
    response = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {JINA_API_KEY}"},
        json={
            "model":      JINA_EMBEDDING_MODEL,
            "task":       task,
            "normalized": True,
            "input":      texts,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = sorted(response.json()["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in data]


def batch(lst, size):
    """Yield successive fixed-size chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def main():
    print("=" * 60)
    print("SurgMentor - Phase 1A: Embedding Pipeline")
    print("=" * 60)

    if not os.path.exists(PREPARED_CASES_FILE):
        raise FileNotFoundError(
            f"{PREPARED_CASES_FILE} not found.\n"
            "Run python scripts/01_prepare_data.py first."
        )

    print(f"\nLoading {PREPARED_CASES_FILE} ...")
    with open(PREPARED_CASES_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)
    print(f"Loaded {len(cases)} cases")

    using_build_path = (CHROMA_BUILD_PATH != CHROMA_DB_PATH)
    build_target = CHROMA_BUILD_PATH if using_build_path else CHROMA_DB_PATH
    print(f"\nConnecting to ChromaDB at {build_target} ...")
    if using_build_path:
        print(f"  (build path override; will copy to {CHROMA_DB_PATH} after build)")

    chroma_client = chromadb.PersistentClient(path=build_target)

    existing_names = [c.name for c in chroma_client.list_collections()]
    if COLLECTION_NAME in existing_names:
        print(f"Existing collection '{COLLECTION_NAME}' found - deleting ...")
        chroma_client.delete_collection(COLLECTION_NAME)

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Collection '{COLLECTION_NAME}' created\n")

    print(f"Embedding {len(cases)} cases in batches of {EMBEDDING_BATCH_SIZE} ...")
    print(f"Model: {JINA_EMBEDDING_MODEL} (retrieval.passage task)\n")

    total_stored = 0
    failed = []

    for batch_cases in tqdm(list(batch(cases, EMBEDDING_BATCH_SIZE)), desc="Embedding"):
        try:
            texts     = [c["text"]     for c in batch_cases]
            ids       = [c["id"]       for c in batch_cases]
            metadatas = [c["metadata"] for c in batch_cases]

            embeddings = get_embeddings(texts, task="retrieval.passage")

            collection.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_stored += len(batch_cases)

        except Exception as e:
            print(f"\nBatch error: {e}")
            for c in batch_cases:
                failed.append(c["id"])

    print("\n" + "=" * 60)
    print(f"Stored  : {total_stored} / {len(cases)} cases")
    if failed:
        print(f"Failed  : {len(failed)} IDs: {failed}")
    print(f"DB path : {CHROMA_DB_PATH}")

    print("\nVerification query: 'acute abdominal pain and fever' ...")
    test_vec = get_embeddings(["acute abdominal pain and fever"], task="retrieval.query")[0]

    results = collection.query(
        query_embeddings=[test_vec],
        n_results=min(2, total_stored),
        include=["documents", "metadatas", "distances"],
    )

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        print(f"\n  Result {i + 1}:")
        print(f"    Case ID   : {meta.get('case_id')}")
        print(f"    Diagnosis : {meta.get('diagnosis')}")
        print(f"    Similarity: {round(1 - dist, 3)}")
        print(f"    Preview   : {doc[:150]}...")

    if using_build_path:
        print(f"\nCopying ChromaDB from {build_target} to {CHROMA_DB_PATH} ...")
        dest = CHROMA_DB_PATH
        for item in os.listdir(dest):
            if item == ".gitkeep":
                continue
            item_path = os.path.join(dest, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
        for item in os.listdir(build_target):
            src = os.path.join(build_target, item)
            dst = os.path.join(dest, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        print(f"Copied. Contents of {CHROMA_DB_PATH}:")
        for item in sorted(os.listdir(CHROMA_DB_PATH)):
            if item != ".gitkeep":
                print(f"  {item}")

    print("\nScript 02 complete. Next: python scripts/03_test_retrieval.py")


if __name__ == "__main__":
    main()
