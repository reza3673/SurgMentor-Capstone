# surgmentor/agent/intent.py
"""
Intent classifier for the AgentController.

Classifies student input into one of 7 IntentCategory values. The classifier
is the PLAN step of the ADK agent loop — it decides what the student wants
before the controller routes to a skill.

Classification strategy (PHASE_4_PLAN.md §4):

  Primary path:   LLM at temperature=0.1 (when SCOPE_CLASSIFICATION_ENABLED=True).
                  Session context (mode, osce_active, osce_step) is included in the
                  prompt so the classifier can distinguish OSCE_TURN from RETRIEVE_CASE.
  Fallback path:  Rule-based keyword matching. Used when the flag is False (tests,
                  low-latency mode) or when any LLM exception occurs.

Safety guarantees:
  - classify_intent() never raises. Returns UNKNOWN on any failure.
  - LLM import is lazy (inside _classify_via_llm). No module-level SOCKS proxy risk.
  - Invalid LLM response (bad JSON, unknown category) → falls back to rule-based.

Course concept: Agent Architecture (Day 2) — explicit intent → skill routing.

Note: CLINICAL_QUESTION is intentionally excluded from MVP. ClinicalReasoningSkill
is a Phase 8 stretch goal. When it is added, append CLINICAL_QUESTION here.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from enum import Enum

from config import DEEPSEEK_CHAT_MODEL, SCOPE_CLASSIFICATION_ENABLED
from surgmentor.memory.session import SessionState


# ── IntentCategory ────────────────────────────────────────────────────────────

class IntentCategory(str, Enum):
    """
    The 7 recognised student intents in SurgMentor.

    Each maps to exactly one skill (or a safe fallback for UNKNOWN).
    OSCE_TURN is the catch-all for mid-session responses — the OSCE override
    rule in the controller ensures any in-session input routes here.

    IntentCategory inherits str so it can be serialised to JSON directly
    (used in TurnSignal.intent_classified field in eval_log.jsonl).
    """
    RETRIEVE_CASE = "RETRIEVE_CASE"   # → CaseRetrievalSkill
    START_OSCE    = "START_OSCE"      # → OSCEExaminerSkill (init)
    OSCE_TURN     = "OSCE_TURN"       # → OSCEExaminerSkill (turn)
    FINISH_OSCE   = "FINISH_OSCE"     # → OSCEExaminerSkill (finish) → EvaluationSkill
    GET_FEEDBACK  = "GET_FEEDBACK"    # → EvaluationSkill
    STUDY_PLAN    = "STUDY_PLAN"      # → StudyPlannerSkill
    UNKNOWN       = "UNKNOWN"         # → static deflection (no skill)


# ── Static responses ──────────────────────────────────────────────────────────

_UNKNOWN_RESPONSE = (
    "I didn't quite understand that. Here is what I can help with:\n\n"
    "- **Show me a case** — retrieve a relevant surgical case to study\n"
    "- **Start OSCE** — begin a structured examination session\n"
    "- **Finish** — end your current OSCE session and receive your score\n"
    "- **How did I do?** — review your last session score\n"
    "- **What should I study?** — receive a personalised study plan\n\n"
    "Try rephrasing your question or choose one of the options above."
)


# ── LLM classification prompt ─────────────────────────────────────────────────

_CLASSIFICATION_PROMPT = """\
You are classifying a student's message in a surgical education system.

Current session context:
  mode: {mode}
  osce_active: {osce_active}
  osce_step: {osce_step}

Student message: "{student_input}"

Classify this message as EXACTLY ONE of:
  RETRIEVE_CASE   — student wants to see a surgical case or learn about a condition
  START_OSCE      — student wants to begin an OSCE examination session
  OSCE_TURN       — student is mid-OSCE and this is their next response to the examiner
  FINISH_OSCE     — student wants to end the current OSCE session
  GET_FEEDBACK    — student wants to see their score or past performance
  STUDY_PLAN      — student wants a personalised study plan or guidance on what to study next
  UNKNOWN         — message is unclear, out of scope, or cannot be classified above

Respond with ONLY a JSON object, no other text:
{{"intent": "<CATEGORY>"}}"""


# ── Surgical keyword list (for rule-based fallback) ───────────────────────────

_SURGICAL_KEYWORDS = {
    "appendic", "cholecyst", "hernia", "bowel", "abdomen", "abdominal",
    "gallbladder", "pancreat", "obstruct", "periton", "laparot", "laparo",
    "colon", "rectal", "sigmoid", "ileostomy", "colostomy", "jaundice",
    "biliary", "hepat", "spleen", "splenic", "thyroid", "parathyroid",
    "breast", "mastect", "vascular", "aortic", "aneurysm", "ischemi",
    "surgical", "surgery", "operation", "operative", "case", "patient",
    "diagnosis", "diagnose", "present", "symptom", "sign", "examine",
    "investigation", "management", "treatment", "clinical",
}


# ── Public interface ──────────────────────────────────────────────────────────

def classify_intent(student_input: str, state: SessionState) -> IntentCategory:
    """
    Classify student input into one of 7 IntentCategory values.

    Primary path:  LLM at temperature=0.1 (when SCOPE_CLASSIFICATION_ENABLED=True).
    Fallback path: Rule-based keyword matching (when flag is False, or on LLM failure).

    Session context (mode, osce_active, osce_step) is forwarded to the classifier
    so it can correctly distinguish OSCE_TURN from RETRIEVE_CASE for mid-session inputs.

    Safety: never raises. Returns UNKNOWN on any unhandled failure.
    """
    if SCOPE_CLASSIFICATION_ENABLED:
        result = _classify_via_llm(student_input, state)
        if result is not None:
            return result
    return _classify_via_rules(student_input, state)


def get_unknown_response() -> str:
    """Return the static help message shown for UNKNOWN intent."""
    return _UNKNOWN_RESPONSE


# ── Private: LLM path ─────────────────────────────────────────────────────────

def _classify_via_llm(student_input: str, state: SessionState) -> IntentCategory | None:
    """
    Call DeepSeek at temperature=0.1 to classify the student input.

    Returns the classified IntentCategory on success.
    Returns None on any exception so the caller falls back to rule-based.
    Lazy import of clients avoids module-level SOCKS proxy error in sandbox.
    """
    try:
        from clients import deepseek  # lazy: not needed until first LLM call
        prompt = _CLASSIFICATION_PROMPT.format(
            mode          = state.mode,
            osce_active   = state.osce_active,
            osce_step     = state.osce_step,
            student_input = student_input[:500],  # truncate for prompt safety
        )
        response = deepseek.chat.completions.create(
            model       = DEEPSEEK_CHAT_MODEL,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.1,
            max_tokens  = 20,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed     = json.loads(raw)
        intent_str = parsed.get("intent", "").upper().strip()
        return IntentCategory(intent_str)          # raises ValueError for unknown values
    except Exception:
        return None                                # caller falls back to rule-based


# ── Private: rule-based fallback ──────────────────────────────────────────────

def _classify_via_rules(student_input: str, state: SessionState) -> IntentCategory:
    """
    Rule-based intent classification.

    Used when SCOPE_CLASSIFICATION_ENABLED=False (tests, low-latency) or when
    the LLM call fails. Covers the most common student input patterns.

    Priority order (highest to lowest):
      1. Explicit OSCE finish signals (osce_active required)
      2. OSCE start signals
      3. Mid-OSCE catch-all (osce_active=True)
      4. Study plan keywords
      5. Feedback / score keywords
      6. Surgical keywords → case retrieval
      7. General retrieval phrases
      8. UNKNOWN (default)
    """
    lower       = student_input.lower().strip()
    osce_active = state.osce_active

    # 1. Explicit finish signals — only meaningful when OSCE is active
    if osce_active and any(w in lower for w in (
        "finish", "done", "end session", "i'm done", "i am done",
        "stop osce", "end osce", "complete session",
    )):
        return IntentCategory.FINISH_OSCE

    # 2. OSCE start signals
    if any(w in lower for w in (
        "start osce", "begin osce", "osce session", "examine me",
        "start examination", "begin examination", "new osce", "osce exam",
        "practice osce", "practise osce", "do an osce",
    )):
        return IntentCategory.START_OSCE

    # 3. Mid-OSCE catch-all: anything when OSCE is active that wasn't a finish
    if osce_active:
        return IntentCategory.OSCE_TURN

    # 4. Study plan
    if any(w in lower for w in (
        "study plan", "what should i study", "help me improve",
        "what to study", "study next", "revision plan", "weak area",
        "study guide", "recommend", "personalised", "personalized",
    )):
        return IntentCategory.STUDY_PLAN

    # 5. Feedback / score review
    if any(w in lower for w in (
        "how did i do", "my score", "my results", "show results",
        "show score", "my performance", "how i did", "past results",
        "previous score", "feedback",
    )):
        return IntentCategory.GET_FEEDBACK

    # 6. Surgical keyword match → case retrieval
    if any(kw in lower for kw in _SURGICAL_KEYWORDS):
        return IntentCategory.RETRIEVE_CASE

    # 7. General retrieval phrases
    if any(w in lower for w in (
        "show me", "give me", "find me", "retrieve", "display",
        "learn about", "tell me about", "what is", "explain",
    )):
        return IntentCategory.RETRIEVE_CASE

    return IntentCategory.UNKNOWN


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("intent.py — import test (rule-based fallback only)")
    print("=" * 60)
    from surgmentor.memory.session import make_default_state

    state_chat = make_default_state("s1", "student-1", mode="chat")
    state_osce = make_default_state("s2", "student-2", mode="osce")
    state_osce.osce_active = True
    state_osce.osce_step   = 2

    cases = [
        ("start osce",               state_chat, IntentCategory.START_OSCE),
        ("show me a case",           state_chat, IntentCategory.RETRIEVE_CASE),
        ("what should I study",      state_chat, IntentCategory.STUDY_PLAN),
        ("how did I do",             state_chat, IntentCategory.GET_FEEDBACK),
        ("I would take a history",   state_osce, IntentCategory.OSCE_TURN),
        ("finish",                   state_osce, IntentCategory.FINISH_OSCE),
        ("asdfghjkl",                state_chat, IntentCategory.UNKNOWN),
    ]
    for text, state, expected in cases:
        result = _classify_via_rules(text, state)
        status = "✅" if result == expected else "❌"
        print(f"  {status}  '{text}' → {result.value}  (expected {expected.value})")

    print("\n✅  Import test PASSED")
