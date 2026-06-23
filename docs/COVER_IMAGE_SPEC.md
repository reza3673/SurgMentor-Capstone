# COVER_IMAGE_SPEC.md — Kaggle Submission Cover Image

**Required:** A cover image must be attached to the Kaggle Media Gallery before the
submit button becomes available. Without it, submission is blocked.

**Format:** PNG, 1600×900 pixels (16:9 landscape)  
**Tools:** Canva, Google Slides, PowerPoint, or Figma — any works

---

## Option A — Full Design (recommended, ~20 min)

### Canvas layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Background: #0D1B2A (deep navy)                                             │
│                                                                              │
│  ┌─ Top-left band ───────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  SurgMentor                                [32pt, white, bold]        │   │
│  │  Agentic Surgical OSCE Trainer             [18pt, #2ECC8F, regular]   │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Centre: Architecture block diagram ─────────────────────────────────┐   │
│  │                                                                       │   │
│  │  [ CLI · Custom Web UI (FastAPI) · Gradio fallback ]                  │   │
│  │         ↓                                                             │   │
│  │  [ Security Layer ]  ←──── pre-flight · post-flight                   │   │
│  │         ↓                                                             │   │
│  │  [ Agent Controller ]  PERCEIVE → PLAN → ACT → OBSERVE               │   │
│  │         ↓                                                             │   │
│  │  [ Skills ]  CaseRetrieval · OSCEExaminer · Evaluation · Planner      │   │
│  │         ↓                                                             │   │
│  │  [ ChromaDB · SQLite · DeepSeek · eval_log.jsonl ]                    │   │
│  │                                                                       │   │
│  │  Use white rounded rectangles on #1A2B3C cards                        │   │
│  │  Arrows in #1E6091 (steel blue)                                       │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Bottom banner ────────────────────────────────────────────────────────┐  │
│  │  Kaggle AI Agents Intensive 2026              Agents for Good  ✦       │  │
│  │  [12pt, #A0B4C8, left]                        [12pt, #2ECC8F, right]  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Colour palette

| Token | Hex | Use |
|-------|-----|-----|
| `--navy` | `#0D1B2A` | Page/canvas background |
| `--navy-card` | `#1A2B3C` | Architecture block backgrounds |
| `--steel` | `#1E6091` | Arrows, borders, secondary text |
| `--green` | `#2ECC8F` | Subtitle, "Agents for Good" badge, accent |
| `--white` | `#FFFFFF` | Primary text, box labels |
| `--muted` | `#A0B4C8` | Footer/caption text |

### Typography

- Title "SurgMentor": 36pt bold, white, sans-serif (Inter, Roboto, or system sans)
- Subtitle: 20pt regular, `#2ECC8F`
- Architecture labels: 11–13pt regular, white
- Bottom banner: 12pt, muted / green

### Step-by-step in Canva

1. New design → Custom size → 1600 × 900 px
2. Background fill → `#0D1B2A`
3. Add text block top-left: "SurgMentor" (36pt bold white) + subtitle (20pt green)
4. Add 5 rounded rectangles vertically centred:
   - Fill `#1A2B3C`, border `#1E6091` 1px, corner radius 8px
   - Labels: "CLI · Custom Web UI · Gradio fallback", "Security Layer", "Agent Controller",
     "Skills", "ChromaDB · SQLite · DeepSeek"
5. Connect blocks with thin `#1E6091` downward arrows
6. Add side labels to Security Layer: "pre-flight" (left arrow in) and
   "post-flight" (right arrow out)
7. Add "PERCEIVE → PLAN → ACT → OBSERVE" as small caption inside Agent Controller block
8. Bottom text bar: left "Kaggle AI Agents Intensive 2026", right "Agents for Good ✦"
9. Export → PNG → 1600 × 900 (check output size before uploading)

---

## Option B — Fast Path (5 minutes)

If time is short before the deadline, use this approach instead:

1. Run `python -m uvicorn server:app --host 0.0.0.0 --port 8000` and open `http://localhost:8000`
2. Click the OSCE nav pill; click Start Session — let the examiner present a case
3. Take a full-screen screenshot of the custom web UI with an active OSCE turn and step progress dots visible
4. Open in any image editor (even Paint / Preview)
5. Add a dark overlay band at the top (70% opacity navy)
6. Add white text over the band: "SurgMentor — Agentic Surgical OSCE Trainer"
7. Add green text below: "Kaggle AI Agents Intensive 2026 · Agents for Good"
8. Crop/resize to exactly 1600 × 900 px
9. Save as PNG

This satisfies the requirement with a real screenshot of the running system —
which also demonstrates that the system actually works, which can only help.

---

## Upload Instructions

1. On the Kaggle Writeup page, click **Media Gallery**
2. Click **Add media → Upload image**
3. Select the PNG file
4. Set it as the **cover image** (there is usually a "Set as cover" toggle)
5. Confirm it appears as the thumbnail preview on the writeup card

**Do not proceed to "Submit" until the cover image appears in the Media Gallery.**
The submit button may be greyed out without it.

---

## File naming

Save the export as: `surgmentor_cover_1600x900.png`

Place a copy in the project root for reference (it will not be committed to git —
add `*.png` to `.gitignore` or leave it out of the repo entirely, since it is a
generated asset not needed for code reproduction).
