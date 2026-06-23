# GAP_ANALYSIS.md

**Source:** PROJECT_UNDERSTANDING.md  
**Date:** 2026-06-20  
**Purpose:** Identify every gap between current SurgMentor and what the Kaggle AI Agents Intensive Capstone requires to win in the "Agents for Good" track.

Gaps are grouped by dimension. Each entry includes severity, why it matters for judging, the recommended fix, estimated effort, and whether it is required for the MVP submission or a stretch goal.

**Severity scale:**
- **Critical** — disqualifies or scores near zero on that criterion without it
- **High** — significant point loss; judges will notice its absence
- **Medium** — detectable gap that reduces competitiveness
- **Low** — polish item; unlikely to be the deciding factor

**Effort scale (solo or small team, 2-week window):**
- **XS** — a few hours
- **S** — half a day to one day
- **M** — 2–3 days
- **L** — 4–6 days
- **XL** — 7+ days; likely incompatible with deadline unless scoped down

---

## Dimension 1: Agent Architecture

### GAP-A1 — No Agent Controller / Orchestration Layer

**Why it matters:** The single highest-weighted criterion is Technical Implementation (50 points). Judges are specifically looking for "meaningful agent use" and "quality of your solution's architecture." Without an agent controller that reasons, routes, and delegates, SurgMentor is a pipeline, not an agent — and judges who took the course will identify this immediately. Submitting without an agent loop is effectively disqualifying for the ADK concept requirement.

**Severity:** Critical

**Recommended fix:** Build a central agent controller class that accepts student input, determines intent (retrieve a case, start OSCE, get feedback, plan study), selects the appropriate skill, invokes it with relevant context, and returns a synthesized response. The loop — perceive → plan → act → observe — must be explicit in code.

**Estimated effort:** L (4–6 days including integration with existing skills)

**MVP required:** Yes

---

### GAP-A2 — No Explicit Skill System

**Why it matters:** Day 3 of the course is entirely dedicated to agent skills as reusable, composable behaviors. The rubric lists "Agent skills (e.g., Agents CLI)" as a demonstrable concept. SurgMentor's current RAG and OSCE logic is monolithic — there are no named, independently invocable skill objects. Judges looking for skill composition will find none.

**Severity:** High

**Recommended fix:** Refactor existing logic into named skill modules: `CaseRetrievalSkill`, `OSCEExaminerSkill`, `ClinicalReasoningSkill`, `EvaluationSkill`, `StudyPlannerSkill`. Each skill should have a clear interface (input schema → output schema), its own system prompt or instruction set, and be independently testable. The agent controller invokes skills by name.

**Estimated effort:** M (2–3 days to refactor and wrap existing logic)

**MVP required:** Yes — at minimum 3 skills must be present and callable

---

### GAP-A3 — No Agent-to-Agent (A2A) Delegation

**Why it matters:** Day 2 covers A2A communication as a key interoperability pattern. Multi-agent design is listed as an optional but high-value concept in SURGMENTOR_MISSION.md. Submissions that demonstrate a Tutor Agent delegating to an OSCE Agent delegating to an Evaluation Agent will score higher on architecture quality than single-agent designs.

**Severity:** Medium

**Recommended fix:** After the single-agent core is working, introduce a lightweight sub-agent pattern: the Orchestrator delegates OSCE session management to an `OSCEAgent` and performance evaluation to an `EvaluationAgent`. Communication can be in-process function calls with structured message passing — full network-level A2A is not required.

**Estimated effort:** M (2–3 days, after GAP-A1 and GAP-A2 are resolved)

**MVP required:** No — stretch goal, but meaningfully increases architecture score

---

### GAP-A4 — No Context Engineering / Memory Layer

**Why it matters:** Day 1 identifies context engineering as the most critical skill in agentic development. An agent that forgets the previous turn in a multi-step OSCE session cannot deliver educational value, and a judge running the demo will notice the broken continuity immediately.

**Severity:** High

**Recommended fix:** Implement session memory: a conversation history object that the agent controller passes to each skill invocation. At minimum, track: current case, current OSCE step, student answers so far, and running score. This does not require a database — an in-memory session state dict is sufficient for demo purposes.

**Estimated effort:** S (1 day — lightweight in-memory session state)

**MVP required:** Yes — without this, multi-turn OSCE simulation does not work

---

## Dimension 2: Competition Concept Requirements

### GAP-C1 — ADK Pattern Not Demonstrated in Code

**Why it matters:** "Agent / Multi-agent system (ADK)" must be demonstrated in code — it is one of the 6 course concepts, and judges must see at least 3. ADK is the most directly observable concept: the code must contain an agent class with a defined reasoning loop, not just LLM calls wrapped in functions.

**Severity:** Critical

**Recommended fix:** Structure the agent controller to explicitly implement the ADK pattern: an agent with a name, a description, a system instruction, a tool registry, and a run loop. Code comments should call out which part of the code implements which ADK concept — judges read comments when evaluating technical implementation.

**Estimated effort:** Covered by GAP-A1 (no additional effort if A1 is done correctly)

**MVP required:** Yes

---

### GAP-C2 — No MCP Server

**Why it matters:** MCP is listed as a demonstrable course concept (must show in code). It also appears as an optional but high-value component in SURGMENTOR_MISSION.md. Implementing even a minimal MCP server that exposes 1–2 surgical education tools signals architectural maturity and directly checks a rubric box.

**Severity:** Medium (it is optional for MVP but raises the score ceiling)

**Recommended fix:** Build a minimal MCP server that exposes `search_surgical_cases` and `evaluate_session` as MCP-compliant tools. The agent controller connects to this MCP server as its tool source rather than calling functions directly. This demonstrates tool discovery and interoperability — exactly what Day 2 teaches.

**Estimated effort:** M (2–3 days; requires MCP library familiarity)

**MVP required:** No — stretch goal. If time is short, skip MCP and demonstrate 3 concepts via ADK + security + deployability.

---

### GAP-C3 — No Security Layer in Code

**Why it matters:** Security features must be demonstrated in code or video. Day 4 teaches security as a first-class, non-optional component. The medical domain makes this especially salient — an agent that could produce unsafe clinical guidance is both a safety risk and a judging liability. The absence of visible guardrails will stand out to any judge familiar with the course.

**Severity:** Critical

**Recommended fix:** Implement a `SecurityLayer` or `GuardrailsModule` with: (1) input sanitizer that rejects patient-identifiable information and detects prompt injection patterns; (2) output filter that appends an educational disclaimer and blocks any response resembling a direct diagnosis or treatment recommendation; (3) least-privilege tool registry that prevents skills from accessing tools outside their defined scope. These must be visible in code, not just mentioned in the README.

**Estimated effort:** S–M (1–2 days for a solid implementation with comments)

**MVP required:** Yes

---

### GAP-C4 — No Evaluation Layer

**Why it matters:** Day 4 explicitly requires evaluation across accuracy, safety, tool selection, user value, and workflow quality. The existing scoring engine produces a numeric score, but it is not wired into an agent-observable evaluation loop. Judges looking for evaluation architecture will not find it.

**Severity:** High

**Recommended fix:** Build an `EvaluationLayer` that runs at the end of each session and produces a structured evaluation report: case retrieval accuracy, OSCE response quality score, safety check pass/fail, skill selection correctness, and session completion status. This report should be logged and surfaced to the student as feedback. The existing scoring engine becomes an input to this layer, not the entire evaluation system.

**Estimated effort:** M (2–3 days to wrap existing scoring and add the structured report)

**MVP required:** Yes — without it, the competition requirement for evaluation is unmet and the Evaluation Skill has nothing to invoke

---

### GAP-C5 — Deployability Not Demonstrated

**Why it matters:** Deployability must be shown in video. The rubric also states the project should be reproducible. A demo that only runs on the author's machine with no setup instructions fails this criterion. Judges specifically want to see that someone else could run this system.

**Severity:** High

**Recommended fix:** Produce a `.env.example` file, a `requirements.txt` or equivalent, and a `README.md` section with exact setup steps. Record the setup portion in the video (even 30 seconds of `pip install && python run.py` succeeding is sufficient). Bonus: deploy to a free hosting tier (Hugging Face Spaces, Railway, or a Kaggle notebook) to provide the required public project link.

**Estimated effort:** S (1 day for repo hygiene + video segment)

**MVP required:** Yes

---

## Dimension 3: Code and Documentation Quality

### GAP-D1 — No README

**Why it matters:** Documentation is worth 20 points — the second-largest single criterion after Technical Implementation. The rubric specifically requires a README with problem, solution, architecture, setup instructions, and diagrams. There is currently no README in the repository.

**Severity:** Critical (zero points on a 20-point criterion without it)

**Recommended fix:** Write a README.md that covers: problem statement (1–2 paragraphs), why agents solve it better than a chatbot, system architecture with a Mermaid or ASCII diagram, skill descriptions, setup instructions (exact commands), environment variable requirements, and a link to the demo video. Aim for completeness over brevity here — judges score on coverage.

**Estimated effort:** S–M (1–2 days, should be written after architecture is finalized)

**MVP required:** Yes

---

### GAP-D2 — No Architecture Diagrams

**Why it matters:** The README criterion, the video criterion, and the writeup criterion all benefit from architecture diagrams. The video rubric explicitly lists "Images and a description of the overall agent architecture." Judges cannot assess architecture quality from code alone in a 5-minute review window.

**Severity:** High

**Recommended fix:** Produce at minimum one diagram showing the agent controller, skills, tools, security layer, and evaluation layer with labeled arrows showing data and control flow. A Mermaid diagram embedded in the README is acceptable and easy to version-control. A separate image export is needed for the Kaggle writeup and video.

**Estimated effort:** XS–S (2–4 hours once architecture is finalized)

**MVP required:** Yes

---

### GAP-D3 — No Inline Code Comments Explaining Architecture

**Why it matters:** The technical implementation rubric explicitly states: "Your code should contain comments pertinent to implementation, design and behaviors." This is not about docstrings on every function — judges want comments that explain *why* an architectural decision was made, which course concept a section implements, and what the agent is doing at each step of its loop.

**Severity:** High

**Recommended fix:** After implementation, do a comment pass on the agent controller, each skill, the security layer, and the evaluation layer. Each major block should have a comment that connects it to a course concept (e.g., `# ADK pattern: agent reasons over available tools before selection`) or explains a design decision (e.g., `# Skills are stateless; session state is managed by the controller to enable independent testability`).

**Estimated effort:** S (half a day dedicated comment pass)

**MVP required:** Yes

---

### GAP-D4 — No .env Pattern / Secret Hygiene

**Why it matters:** The competition rules explicitly warn: "DO NOT INCLUDE ANY API KEYS OR PASSWORDS IN YOUR CODE." Violation is grounds for disqualification. The production-grade checklist from Day 5 also requires `.env` usage. Currently, API credentials for DeepSeek and any other services are managed in an unknown way.

**Severity:** Critical (disqualification risk)

**Recommended fix:** Audit all source files for hardcoded credentials. Move all API keys and secrets to environment variables loaded via a `.env` file. Commit a `.env.example` with placeholder values. Add `.env` to `.gitignore`. Verify no secrets appear in git history before making the repository public.

**Estimated effort:** XS (2–4 hours; higher if secrets are deeply embedded)

**MVP required:** Yes

---

## Dimension 4: Submission Deliverables

### GAP-S1 — No YouTube Video

**Why it matters:** A public YouTube video is a mandatory submission component. Without it, the submission is invalid and receives zero points on the 10-point video criterion. The video also supports the Antigravity concept demonstration, which can only be shown in video.

**Severity:** Critical (invalid submission without it)

**Recommended fix:** Record a structured 5-minute video: problem statement (45s), why agents (45s), architecture walkthrough with diagram (60s), live OSCE session demo (90s), code highlight of the agent loop (30s), closing (30s). Use screen recording for the demo portions. Publish unlisted to YouTube; attach to the Kaggle Media Gallery.

**Estimated effort:** M (2–3 days including preparation, recording, and light editing — schedule this explicitly)

**MVP required:** Yes

---

### GAP-S2 — No Kaggle Writeup

**Why it matters:** The Kaggle Writeup is a mandatory submission component and worth 10 points. It must be submitted before the July 6 deadline — draft writeups are not considered.

**Severity:** Critical (invalid submission without it)

**Recommended fix:** Write the writeup as a narrative in this structure: problem context → why agents → architecture decisions → skills and tools built → security approach → what was learned → what could be improved. Include 1–2 inline images (architecture diagram, demo screenshot). Stay under 2,500 words. Draft this in parallel with the video, not after.

**Estimated effort:** S (1 day, but requires architecture and demo to be complete first)

**MVP required:** Yes

---

### GAP-S3 — No Public Project Link / Demo

**Why it matters:** A public project link is a mandatory submission component. Without a live demo or public GitHub with setup instructions, the submission is invalid.

**Severity:** Critical (invalid submission without it)

**Recommended fix:** At minimum, publish the code to a public GitHub repository with a complete README before the deadline. As a stretch goal, deploy a Gradio or Streamlit interface to Hugging Face Spaces or a free cloud tier so judges can interact with the system without local setup.

**Estimated effort:** S for GitHub-only (1 day); M–L for hosted deployment (2–4 days depending on hosting complexity)

**MVP required:** Yes (GitHub + README is sufficient; hosted demo is stretch)

---

### GAP-S4 — No Cover Image / Media Gallery

**Why it matters:** A cover image is required to submit the Kaggle Writeup. Without it, the submission cannot be finalized.

**Severity:** Critical (blocks submission)

**Recommended fix:** Create a simple, clean cover image: SurgMentor logo or name, a brief tagline, and the architecture diagram or a screenshot of the running system. Any image editing tool or even a well-composed screenshot is sufficient.

**Estimated effort:** XS (1–2 hours)

**MVP required:** Yes

---

## Gap Summary Table

| Gap ID | Name | Severity | MVP | Effort |
|---|---|---|---|---|
| GAP-A1 | No agent controller / orchestration layer | Critical | Yes | L |
| GAP-A2 | No explicit skill system | High | Yes | M |
| GAP-A3 | No agent-to-agent delegation | Medium | No (stretch) | M |
| GAP-A4 | No context engineering / memory layer | High | Yes | S |
| GAP-C1 | ADK pattern not demonstrated in code | Critical | Yes | (covered by A1) |
| GAP-C2 | No MCP server | Medium | No (stretch) | M |
| GAP-C3 | No security layer in code | Critical | Yes | S–M |
| GAP-C4 | No evaluation layer | High | Yes | M |
| GAP-C5 | Deployability not demonstrated | High | Yes | S |
| GAP-D1 | No README | Critical | Yes | S–M |
| GAP-D2 | No architecture diagrams | High | Yes | XS–S |
| GAP-D3 | No inline architecture comments | High | Yes | S |
| GAP-D4 | No .env pattern / secret hygiene | Critical | Yes | XS |
| GAP-S1 | No YouTube video | Critical | Yes | M |
| GAP-S2 | No Kaggle writeup | Critical | Yes | S |
| GAP-S3 | No public project link / demo | Critical | Yes | S (GitHub) |
| GAP-S4 | No cover image / media gallery | Critical | Yes | XS |

**Critical gaps:** 9  
**High gaps:** 6  
**Medium gaps:** 2  
**Low gaps:** 0  

**MVP-required gaps:** 15 out of 17  
**Stretch gaps:** GAP-A3 (A2A delegation), GAP-C2 (MCP server)

---

## Sequencing Recommendation

The gaps should be closed in this order to avoid rework and ensure the MVP is submission-ready before the deadline:

**Phase 1 — Architecture (before any code):** Finalize architecture proposal addressing GAP-A1, GAP-A2, GAP-A4, GAP-C1. No code until architecture is approved.

**Phase 2 — Core implementation:** Build agent controller (A1/C1) → skill system (A2) → session memory (A4) → security layer (C3) → evaluation layer (C4).

**Phase 3 — Repository hygiene:** Secret audit (D4) → .env pattern → .gitignore → public GitHub repo (S3).

**Phase 4 — Documentation:** Architecture diagrams (D2) → README (D1) → inline comments (D3).

**Phase 5 — Submission deliverables:** Cover image (S4) → video recording (S1) → Kaggle writeup (S2) → final submission.

**Phase 6 — Stretch goals (if time permits):** A2A delegation (A3) → MCP server (C2) → hosted deployment upgrade (S3 stretch).
