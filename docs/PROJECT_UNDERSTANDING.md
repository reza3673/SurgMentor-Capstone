# PROJECT_UNDERSTANDING.md

## 1. Competition Understanding

**Competition:** Kaggle AI Agents Intensive — Vibe Coding Capstone Project  
**Sponsor:** Google  
**Track selected:** Agents for Good  
**Deadline:** July 6, 2026 at 11:59 PM PT  
**Prize:** Non-monetary (Kaggle swag, 3 winners per track)  
**License:** CC-BY 4.0 — all winning code becomes open source

This is a hackathon, not a scored leaderboard competition. Each team submits once. Judges evaluate the submission holistically using a rubric. There is no test dataset — the work product itself is the submission.

A valid submission requires all four of:
1. Kaggle Writeup (max 2,500 words)
2. Media Gallery with cover image
3. Public YouTube video (max 5 minutes)
4. Public project link (live demo or GitHub with setup instructions)

The submission must demonstrate **at least 3** of the 6 key course concepts in code or video.

---

## 2. Evaluation Criteria Summary

Total: **100 points**

### Category 1 — The Pitch (30 points)

| Criterion | Points | What Judges Want |
|---|---|---|
| Core Concept & Value | 10 | Clear problem, meaningful use of agents, innovation |
| YouTube Video | 10 | Problem statement, agent rationale, architecture, demo, build process |
| Writeup | 10 | Well-articulated problem, solution, architecture, journey |

### Category 2 — The Implementation (70 points)

| Criterion | Points | What Judges Want |
|---|---|---|
| Technical Implementation | 50 | Architecture quality, code quality, meaningful agent use, clever tool use, code comments |
| Documentation | 20 | README covering problem, solution, architecture, setup instructions, diagrams |

**Key insight:** 70% of the score is technical. Code quality, architecture, and documentation are the primary levers for winning.

### Required Course Concepts (must demonstrate ≥ 3)

| Concept | Demonstrate In |
|---|---|
| Agent / Multi-agent system (ADK) | Code |
| MCP Server | Code |
| Antigravity | Video |
| Security features | Code or Video |
| Deployability | Video |
| Agent skills (e.g., Agents CLI) | Code or Video |

---

## 3. Key Concepts from the Course

### Day 1 — The New SDLC
- The developer role shifts from coder to architect/orchestrator
- **Context engineering** is the most critical skill: agent quality depends on context, instructions, memory, tools, and evaluation — not just the model
- The harness (prompts + tools + memory + routing + evaluation + security) is the product
- Build agent systems, not chatbots

### Day 2 — Tools and Interoperability
- Agents become useful through external system interaction
- **MCP (Model Context Protocol):** standardized tool access and discovery
- **A2A (Agent-to-Agent):** agents delegate to specialized sub-agents
- Prefer modular, composable components over monolithic designs

### Day 3 — Agent Skills
- Skills are reusable, specialized behaviors (not models)
- Benefits: smaller context, better scalability, easier evaluation
- Complex workflows are built by composing multiple skills

### Day 4 — Security and Evaluation
- Security and evaluation are first-class, non-optional components
- Security principles: least privilege, guardrails, human-in-the-loop, prompt sanitization, context hygiene
- Evaluation dimensions: accuracy, safety, tool selection, user value, workflow quality

### Day 5 — Production-Grade Development
- Spec-driven: requirements → architecture → implementation → testing → evaluation → deployment
- Production checklist: comprehensive README, no secrets in repo (.env pattern), testable core workflows, reproducible deployment

---

## 4. What Makes an AI Agent in This Competition

The competition defines an agent as a system that:
- **Reasons** — not just retrieves; makes decisions
- **Takes action** — invokes tools, calls external systems
- **Completes complex tasks** — multi-step, not single-turn
- **Uses ADK or equivalent architecture** — structured agent controller with defined skills
- **Delegates** — routes sub-tasks to specialized components (multi-agent bonus)

A chatbot with RAG is not an agent. An agent perceives state, selects tools, executes plans, and self-evaluates — the loop matters, not just the output.

The judges will look for **meaningful** agent use: agents must be central to the solution, not decorative.

---

## 5. What SurgMentor Currently Is

SurgMentor is a RAG-based surgical education application with the following components:

| Component | Technology |
|---|---|
| LLM | DeepSeek API |
| Vector store | ChromaDB |
| Embeddings | Jina Embeddings |
| Retrieval | Surgical RAG pipeline |
| Simulation | OSCE Simulation module |
| Scoring | Performance scoring engine |

**Current capabilities:**
- Retrieve surgical cases from a vector database
- Simulate OSCE (Objective Structured Clinical Examination) sessions
- Score student performance

**Current limitations (from SURGMENTOR_MISSION.md):**
- No ADK architecture (no agent controller layer)
- No MCP integration (tools are not MCP-compliant)
- No explicit skill system (behaviors are monolithic, not composable)
- No agent orchestration layer (no routing between specialized components)
- Limited evaluation architecture (scoring exists but is not an agent-observable evaluation loop)

In its current state, SurgMentor is a prototype pipeline, not an agent system. It cannot qualify for this competition without significant architectural transformation.

---

## 6. What SurgMentor Needs to Become

SurgMentor must transform into a multi-skill, agent-orchestrated surgical education system. The target architecture:

### Agent Controller
A central orchestrator that receives student intent, selects the appropriate skill, routes the workflow, and synthesizes results.

### Skills (reusable, composable)
| Skill | Function |
|---|---|
| Case Retrieval Skill | Search ChromaDB for relevant surgical cases |
| OSCE Examiner Skill | Conduct structured OSCE sessions step-by-step |
| Clinical Reasoning Skill | Guide differential diagnosis and decision-making |
| Evaluation Skill | Score session performance against rubric |
| Study Planner Skill | Generate personalized remediation plans |

### MCP Tools (optional but high-value)
Expose core capabilities as MCP-compliant tools:
- `search_surgical_cases`
- `retrieve_osce_case`
- `evaluate_session`
- `generate_study_plan`

### Security Layer
- Input sanitization (no patient-identifiable data, no prompt injection)
- Output guardrails (educational use only, no diagnosis, no treatment recommendations)
- Least privilege on tool access
- No fabricated clinical details

### Evaluation Layer
Agent-observable evaluation that measures:
- Accuracy of case retrieval
- Safety of outputs
- Correct tool selection
- Educational value delivered
- Workflow completion quality

### Deployable Demo
- Public GitHub repository with complete setup instructions
- `.env.example` with no secrets committed
- Architecture diagrams
- Runnable demo (local or hosted)

---

## 7. Risks and Gaps

### Technical Risks
| Risk | Severity | Mitigation |
|---|---|---|
| ADK integration complexity | High | Start with a minimal agent loop before adding skills |
| MCP server setup | Medium | MCP is optional; implement only if time permits |
| ChromaDB + new architecture compatibility | Medium | Abstract the retrieval layer early |
| DeepSeek API rate limits or instability | Medium | Add fallback model config via environment variable |
| Multi-agent routing bugs | High | Test each skill in isolation before integration |

### Scope Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Over-engineering before validation | High | Follow spec-driven workflow: spec first, code second |
| Insufficient time for video + writeup | High | Reserve last 2 days for non-code deliverables |
| Demo not publicly accessible | Medium | Target local-runnable demo; hosting is a bonus |

### Medical Domain Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Agent produces unsafe clinical content | Critical | Hard guardrails: educational disclaimer on every output |
| Fabricated surgical case details | High | RAG-only answers; no hallucinated case facts |
| Student misuses system for real diagnosis | Medium | Clear scope language in README and UI |

### Competition Gaps (current state)
- No demonstrated agent loop → must build
- No code comments pertinent to implementation → must add
- No README → must write
- No architecture diagrams → must produce
- No video → must record
- No Kaggle writeup → must draft

---

## 8. Recommended Strategy for Maximizing Judging Score

### Priority Stack (ordered by score impact)

**Priority 1 — Technical Implementation (50 points)**
Build a clean, well-commented agent system with:
- An agent controller that routes to named skills
- At minimum 3 skills fully implemented (OSCE Examiner, Case Retrieval, Evaluation)
- Demonstrated course concepts in code (ADK pattern + security + at least one of MCP/skills)
- Inline comments explaining architectural decisions, not just what the code does

**Priority 2 — Documentation (20 points)**
Produce a README that:
- Opens with the problem and why agents solve it better than a chatbot
- Contains an architecture diagram (even a clear ASCII or Mermaid diagram)
- Provides exact setup steps that a stranger can follow
- Links to the demo video and live demo (or Kaggle notebook)

**Priority 3 — Writeup (10 points)**
Write the Kaggle writeup as a narrative:
- Problem → agent insight → architecture decisions → what was built → what was learned
- Include 1-2 architecture images inline
- Stay under 2,500 words; aim for 1,800-2,000

**Priority 4 — Video (10 points)**
Structure the 5-minute video as:
1. Problem (45 seconds)
2. Why agents (45 seconds)
3. Architecture walkthrough with diagram (60 seconds)
4. Live demo of OSCE session (90 seconds)
5. Code highlight of one key agent decision loop (30 seconds)
6. Wrap (30 seconds)

**Priority 5 — Core Concept & Value (10 points)**
The "Agents for Good" track rewards genuine educational value. SurgMentor's domain — surgical resident training — is a compelling, clearly-scoped problem with demonstrable real-world impact. Lean into this in the pitch.

### Minimum Viable Demonstration (to satisfy judging rubric)
Demonstrate these 3 course concepts:
1. **Agent / Multi-agent system (ADK)** — agent controller with skill routing (in code)
2. **Security features** — input guardrails + output safety layer (in code)
3. **Deployability** — reproducible local setup shown in video

Stretch goals if time permits:
4. **Agent skills** — named, composable skill objects (in code)
5. **MCP Server** — expose 1-2 tools as MCP-compliant endpoints (in code)

### Architectural Principle to Follow
Keep the implementation honest to the course philosophy: the agent should reason, select tools, and self-evaluate — not just wrap RAG in an agent frame. The agent loop itself must be visible in the code and demonstrable in the video. Judges who know the course material will recognize shallow implementations.

### What to Avoid
- Do not start coding before architecture is approved
- Do not build MCP first — it is optional; build the agent core first
- Do not commit API keys or use hardcoded secrets
- Do not exceed 2,500 words in the writeup
- Do not submit a chatbot with a renamed system prompt as an "agent"
