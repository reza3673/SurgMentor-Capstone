# surgmentor/skills/case_retrieval_skill.py
"""
CaseRetrievalSkill — find and present relevant surgical cases for student learning.

This skill powers the free-chat mode. It:
  1. Embeds the student query via Jina (inside search_vector_store)
  2. Retrieves the top-K most similar cases from ChromaDB
  3. Uses the student's weak_areas to bias retrieval toward learning gaps (Day 1 context engineering)
  4. Calls DeepSeek to present the cases in an educational, pedagogically grounded narrative
  5. Appends source citations so the student knows which cases were used

Context engineering (Day 1): weak_areas from bundle.student_profile are passed as
bias_topics to search_vector_store. This augments the query with the student's gap areas
before embedding, steering retrieval toward cases the student most needs to see.

Grounding rule: the LLM is explicitly instructed to use ONLY information from the
retrieved cases. It may not introduce clinical facts not present in those cases.
Source citations are appended to every response to make grounding visible.

Streaming variant: run_streaming() yields chunks from the DeepSeek streaming API.
Used by the Gradio interface (Phase 5). The controller always calls run() (non-streaming).

Permitted tools: search_vector_store, format_case_context
LLM role: educational tutor at temperature=0.7

Design reference (read-only): surgery-rag/rag_engine.py (chat branch),
surgery-rag/services/chat_service.py — message structure and source citation format.
All code rewritten from scratch.

Course concept: Agent Skills (Day 3), Context Engineering (Day 1)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEEPSEEK_CHAT_MODEL, TOP_K_RESULTS, HISTORY_WINDOW
from surgmentor.skills.base import ContextBundle, Skill, SkillResult
from surgmentor.rag import retrieval_tool          # module-level; patchable in tests
import surgmentor.memory.db_store as db_store      # module-level; patchable in tests


# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_CHAT = """You are a surgical education tutor helping medical students learn \
from clinical case studies.

Your role:
1. Present the provided surgical case(s) in a clear, educational format.
2. Highlight the key clinical features most relevant to the student's question.
3. Guide the student's reasoning with focused explanations — Socratic where appropriate.
4. Ask a follow-up question at the end if it deepens the student's understanding.

CRITICAL CONSTRAINTS:
- Use ONLY information from the case descriptions provided below.
  Do not introduce clinical facts, statistics, drug doses, or management protocols
  not present in those cases.
- Frame all content as educational — this is a learning tool, not a clinical
  decision-support system. Do not provide advice for managing real patients.
- When drawing from a specific case, state which case you are referencing."""

_GROUNDING_GUARD = (
    "REMINDER: Respond using only information from the provided cases. "
    "Do not add clinical details not present in the case descriptions above."
)

_RETRIEVAL_FALLBACK = (
    "I encountered an issue retrieving case information. "
    "Please try again or rephrase your question."
)

_NO_CASES_MESSAGE = (
    "No relevant surgical cases were found for your query.\n\n"
    "Try rephrasing using clinical terms (e.g., \"right iliac fossa pain\", "
    "\"acute abdomen\", \"obstructive jaundice\") or ask about a specific surgical condition."
)


# ── CaseRetrievalSkill ────────────────────────────────────────────────────────

class CaseRetrievalSkill(Skill):
    """
    Find and present relevant surgical cases for student learning.

    Course concepts:
      Agent Skills (Day 3)       — composable, stateless, independently testable
      Context Engineering (Day 1) — weak_areas bias retrieval toward student gaps

    Input (from ContextBundle):
      student_input   the student's query
      weak_areas      past OSCE weak areas → passed as bias_topics to retrieval
      session_history windowed conversation history (last HISTORY_WINDOW turns)
      student_id      for db_store.log_topics()
      parameters      {"top_k": int} — optional override for retrieval count

    Output (SkillResult):
      response_text   educational case presentation + source citations
      metadata        {"retrieval_hits": int, "case_ids": list[str]}
    """

    name        = "CaseRetrievalSkill"
    description = "Find and present relevant surgical cases for student learning."

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, bundle: ContextBundle) -> SkillResult:
        """
        Retrieve relevant cases and present them educationally.

        Step 1: Retrieve — search_vector_store with optional bias_topics.
        Step 2: Guard — if empty, return informative message without LLM call.
        Step 3: Build context block from retrieved cases.
        Step 4: Log topics studied to SQLite (best-effort, swallows exceptions).
        Step 5: Call DeepSeek with grounded context.
        Step 6: Append source citations.
        Step 7: Return SkillResult.
        """
        top_k = bundle.parameters.get("top_k", TOP_K_RESULTS)

        # ── Step 1: Retrieve ──────────────────────────────────────────────────
        # bias_topics (Context Engineering — Day 1): weak-area strings are
        # appended to the query before Jina embedding, e.g.
        #   "appendicitis [focus: haemostasis; wound closure]"
        # This biases cosine similarity toward cases the student most needs —
        # without changing what they asked. Implemented in retrieval_tool.py.
        cases = retrieval_tool.search_vector_store(
            query       = bundle.student_input,
            top_k       = top_k,
            bias_topics = bundle.weak_areas,
        )

        # ── Step 2: Empty-result guard ────────────────────────────────────────
        if not cases:
            return SkillResult(
                response_text = _NO_CASES_MESSAGE,
                metadata      = {"retrieval_hits": 0, "case_ids": []},
            )

        # ── Step 3: Build case context ────────────────────────────────────────
        case_context = retrieval_tool.format_case_context(cases)

        # ── Step 4: Log topics (best-effort) ─────────────────────────────────
        try:
            db_store.register_student(bundle.student_id)
            db_store.log_topics(bundle.student_id, cases, mode="chat")
        except Exception:
            pass  # logging failure must never break the student's response

        # ── Step 5: LLM call ──────────────────────────────────────────────────
        # Apply history window: OSCE history is full; chat history is windowed.
        history_window = bundle.session_history[-HISTORY_WINDOW:]
        messages = [
            {"role": "system",
             "content": SYSTEM_PROMPT_CHAT + "\n\nRELEVANT CASES:\n" + case_context},
            {"role": "system",
             "content": _GROUNDING_GUARD},
            *history_window,
            {"role": "user", "content": bundle.student_input},
        ]
        response_text = self._call_retrieval_llm(messages)

        # ── Step 6: Append citations ──────────────────────────────────────────
        sources_block = "\n\n**Sources:**\n" + self._format_sources(cases)
        full_response = response_text + sources_block

        # ── Step 7: Return ────────────────────────────────────────────────────
        return SkillResult(
            response_text = full_response,
            metadata      = {
                "retrieval_hits": len(cases),
                "case_ids":       [c.case_id for c in cases],
                "biased_by_weak_areas": bool(bundle.weak_areas),
            },
        )

    def run_streaming(self, bundle: ContextBundle):
        """
        Streaming variant for Gradio (Phase 5). Yields response chunks.

        The citation block is yielded as the final chunk after all LLM chunks.
        The controller always calls run() (non-streaming); the Gradio app calls
        run_streaming() directly to enable real-time token streaming.

        Usage:
            for chunk in skill.run_streaming(bundle):
                print(chunk, end="", flush=True)
        """
        top_k = bundle.parameters.get("top_k", TOP_K_RESULTS)
        cases = retrieval_tool.search_vector_store(
            query=bundle.student_input, top_k=top_k, bias_topics=bundle.weak_areas)

        if not cases:
            yield _NO_CASES_MESSAGE
            return

        case_context = retrieval_tool.format_case_context(cases)
        try:
            db_store.register_student(bundle.student_id)
            db_store.log_topics(bundle.student_id, cases, mode="chat")
        except Exception:
            pass

        history_window = bundle.session_history[-HISTORY_WINDOW:]
        messages = [
            {"role": "system",
             "content": SYSTEM_PROMPT_CHAT + "\n\nRELEVANT CASES:\n" + case_context},
            {"role": "system", "content": _GROUNDING_GUARD},
            *history_window,
            {"role": "user", "content": bundle.student_input},
        ]
        try:
            from clients import deepseek
            stream = deepseek.chat.completions.create(
                model=DEEPSEEK_CHAT_MODEL, messages=messages,
                temperature=0.7, max_tokens=600, stream=True)
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception:
            yield _RETRIEVAL_FALLBACK

        yield "\n\n**Sources:**\n" + self._format_sources(cases)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _call_retrieval_llm(self, messages: list[dict]) -> str:
        """
        Call DeepSeek and return the response text.

        Lazy import of clients avoids module-level SOCKS proxy error in sandbox.
        Returns the fallback string on any exception — retrieval must never crash.
        """
        try:
            from clients import deepseek  # lazy: not needed until first LLM call
            response = deepseek.chat.completions.create(
                model       = DEEPSEEK_CHAT_MODEL,
                messages    = messages,
                temperature = 0.7,
                max_tokens  = 600,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return _RETRIEVAL_FALLBACK

    def _format_sources(self, cases: list) -> str:
        """
        Format retrieved cases as a citation block.

        Output format:
          - Case 1: case_1 — Acute appendicitis (similarity: 0.72)
          - Case 2: case_2 — Cholecystitis (similarity: 0.68)
        """
        lines = []
        for i, c in enumerate(cases, 1):
            meta      = c.metadata if c.metadata else {}
            diagnosis = meta.get("diagnosis", "Unknown")
            lines.append(
                f"  - Case {i}: {c.case_id} — {diagnosis} (similarity: {c.similarity:.2f})"
            )
        return "\n".join(lines)


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("case_retrieval_skill.py — import test")
    print("=" * 60)
    from surgmentor.skills.base import Skill
    skill = CaseRetrievalSkill()
    assert isinstance(skill, Skill)
    assert skill.name == "CaseRetrievalSkill"
    print(f"✅  CaseRetrievalSkill instantiated: name='{skill.name}'")
    print("    HISTORY_WINDOW =", HISTORY_WINDOW)
    print("    TOP_K_RESULTS  =", TOP_K_RESULTS)
    print("\n✅  Import test PASSED (no LLM or ChromaDB calls made)")
