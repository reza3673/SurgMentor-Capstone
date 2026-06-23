# surgmentor/rag/__init__.py
"""
RAG / tool layer: ChromaDB retrieval and case formatting tools.

Provides search_vector_store() and get_case_by_id() — the only tools
that may read from the vector knowledge base. Skills call these tools;
they never touch ChromaDB directly.

Phase 1 implementation target.
"""
