# VIDEO_SCRIPT_FINAL.md — SurgMentor Demo Video

**Target duration:** 4:30–4:50 (hard cap: 5:00)  
**Upload destination:** YouTube (public)  
**Format:** Screen capture + voiceover. No face camera required.

---

## Pre-recording Checklist

```
□  python -m uvicorn server:app --host 0.0.0.0 --port 8000 running — no errors in terminal
□  Browser open at http://localhost:8000 — SurgMentor custom web UI loaded
□  OSCE view visible (click OSCE nav pill) — step progress dots showing, "Not started" pill
□  Browser at 100% zoom, notifications disabled
□  VS Code open to surgmentor/agent/controller.py, scrolled to run() method, Steps 1–11 visible
□  Terminal window available (for eval_log inspection in Segment 5)
□  OBS or screen capture software armed — audio levels normal
□  Phone silent, email/Slack notifications off
□  Dry run completed — total time under 4:50
```

---

## Segment 1 — The Problem  
**⏱ 0:00–0:45 (45 seconds)**  
**Screen:** Title card or plain dark background with "SurgMentor" text

> Surgical residents learn clinical reasoning through OSCE examinations — Objective
> Structured Clinical Examinations. In an OSCE, a trained examiner presents a patient
> case, asks a structured sequence of clinical questions, and scores the trainee's
> reasoning against a rubric. It is the gold standard for surgical education.
>
> The problem: expert examiners are scarce and expensive. Residents at major teaching
> hospitals get regular structured practice. Residents elsewhere — at smaller hospitals,
> in lower-resource settings, or outside formal rotations — get far less. Clinical
> reasoning degrades without deliberate practice.
>
> SurgMentor is an agent that acts as that examiner. Available 24/7, consistent scoring,
> and personalised feedback — without requiring a human expert to be present.

**[45 seconds — cue Segment 2]**

---

## Segment 2 — Why Agents?  
**⏱ 0:45–1:30 (45 seconds)**  
**Screen:** Switch to architecture diagram — display `docs/assets/surgmentor_architecture_1600x900.png` (or open `docs/architecture.md` in VS Code preview)

> A RAG pipeline alone can't solve this problem. RAG can fetch a relevant surgical case
> — but it can't maintain a multi-turn examination, apply a consistent scoring rubric,
> switch between teaching and examining modes, or adapt to the student's specific
> weak areas from past sessions.
>
> An agent loop adds what RAG cannot: intent classification — so the system knows
> whether to retrieve a case, conduct an exam, or generate a study plan. Session-level
> memory — so the examiner remembers every answer. Four composable skills that the
> controller routes to based on context. And structured evaluation — every turn writes
> a signal to an audit log.
>
> This is the design the AI Agents Intensive course teaches, and it is exactly right
> for this problem.

**[45 seconds — cue Segment 3]**

---

## Segment 3 — Architecture  
**⏱ 1:30–2:30 (60 seconds)**  
**Screen:** Stay on `docs/assets/surgmentor_architecture_1600x900.png`

> Here is the full architecture. Five layers.
>
> Entry interfaces — a CLI, a custom FastAPI web application, and an optional
> Gradio fallback. All three call the same controller with the same interface.
> No business logic lives in the interface layer.
>
> Security layer — two mandatory passes on every turn. Pre-flight: PII detection,
> prompt injection heuristics, length limits, hard-block clinical danger patterns.
> Post-flight: medical disclaimer injection, OSCE step tags, clinical assertion removal.
> It cannot be bypassed.
>
> The agent controller — this is the ADK loop. Perceive: read session state.
> Plan: classify intent, apply the OSCE session override, build a trimmed context
> bundle for the skill. Act: invoke the skill — the controller never calls the LLM
> directly. Observe: filter output, log a TurnSignal, update state.
>
> Four skills: CaseRetrievalSkill searches ChromaDB with weak-area bias. The OSCE
> Examiner runs the three-phase examination — init, turn, finish. EvaluationSkill
> scores with a structured rubric. StudyPlannerSkill generates personalised plans
> from historical weak areas.
>
> At the bottom: ChromaDB for case vectors, SQLite for student profiles, and the
> eval log — one JSON object per turn.

**[60 seconds — cue Segment 4]**

---

## Segment 4 — Live Demo  
**⏱ 2:30–4:00 (90 seconds)**  
**Screen:** Browser — http://localhost:8000 — SurgMentor custom web UI

> Here is the system running. Three views: Chat, OSCE, and Profile — accessed via the
> navigation pills at the top.

**[Chat view is active. Type: `show me a case about right iliac fossa pain`]**

> The agent classifies this as RETRIEVE_CASE. CaseRetrievalSkill embeds the query,
> searches ChromaDB — biasing toward this student's weak areas — and returns the
> top cases with source citations at the bottom of the response.

**[Click the OSCE nav pill to switch to OSCE view. Click the "Start Session" button.]**

> Now it classifies as START_OSCE. The OSCE Examiner presents a patient case —
> [read the first sentence of the case aloud] — and asks the opening clinical question.
> Notice the six-step progress indicator: Step 1 of 6 is now active.

**[Type a clinical response — e.g., "I would take a focused history starting with the onset and character of the pain."]**

> The OSCE session override means every input while a session is active is routed to
> OSCEExaminerSkill, regardless of what the intent classifier returns. The examiner
> follows up, and the step indicator advances.

**[Type one more clinical response — e.g., "I would examine for guarding and rebound tenderness in the right iliac fossa."]**

**[Click the "End & Score" button.]**

> EvaluationSkill scores the session — [read the score aloud: "Score: X out of 10."]
> The score panel appears with feedback, weak areas extracted, and study recommendations.

**[Click the Profile nav pill to switch to Profile view. Click "Refresh Stats".]**

> This session is now in the historical record. The next case retrieval will be biased
> toward the weak areas identified here. Click "Generate Study Plan" and the
> StudyPlannerSkill reads the accumulated weak areas and returns a personalised plan.

**[90 seconds — cue Segment 5]**

---

## Segment 5 — Code Highlight  
**⏱ 4:00–4:30 (30 seconds)**  
**Screen:** VS Code — surgmentor/agent/controller.py — scrolled to run() method, Steps 1–11 visible

> Two things to point out.
>
> The controller's run method — you can see the ADK pattern labelled explicitly at
> every step: PERCEIVE, PLAN, ACT, OBSERVE. The security layer is wired at Step 2
> before any skill is called, and at Step 8 before the response reaches the student.
>
> [Switch to terminal. Run: `python -c "import json; [print(json.dumps(json.loads(l), indent=2)) for l in open('eval_log.jsonl')][-1:]"`]
>
> And the eval log — one JSON entry per turn, machine-readable, no extra tooling.

**[30 seconds — cue Segment 6]**

---

## Segment 6 — Wrap  
**⏱ 4:30–4:50 (20 seconds)**  
**Screen:** GitHub repository page (once published)

> SurgMentor is open source, MIT licensed. The repository is linked in the submission.
> Three commands from clone to a running system — no cloud infrastructure required.
>
> Agents for Good: making structured surgical OSCE practice available to every resident,
> regardless of where they train.

**[End — total: ~4:45]**

---

## Timing Summary

| Segment | Content | Target |
|---------|---------|--------|
| 1 | Problem | 0:45 |
| 2 | Why Agents? | 0:45 |
| 3 | Architecture | 1:00 |
| 4 | Live Demo | 1:30 |
| 5 | Code Highlight | 0:30 |
| 6 | Wrap | 0:20 |
| **Total** | | **4:50** |

If running long during the dry run, trim Segment 4 first: reduce to one student
response before clicking Finish. Never cut Segment 2 (the agent rationale) or
Segment 3 (architecture) — judges score on these.

---

## Recovery Notes

| Situation | Recovery |
|-----------|----------|
| LLM response takes > 15 seconds | Say "responses typically take 1–3 seconds; this is a development environment" and wait |
| FastAPI / web UI throws an error | Switch to `python app.py` (Gradio fallback at localhost:7860) — the demo steps are the same, just different UI styling |
| Browser zoom resets | Ctrl+0 to restore 100% |
| eval_log.jsonl command fails | Skip Segment 5 terminal portion; describe the format verbally while showing the code |
