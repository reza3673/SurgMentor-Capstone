# SurgMentor Frontend Redesign Plan

**Status:** Awaiting approval before implementation  
**File to modify:** `web/index.html` (single-file SPA — all HTML, CSS, JS in one file)  
**Files that do NOT change:** All Python files, FastAPI server, skills, tests, `requirements.txt`, `config.py`

---

## 1. Current UI Weaknesses

### Global
| Issue | Detail |
|---|---|
| No web font loaded | `Inter` is declared but never fetched — falls back to system font stack, inconsistent cross-platform |
| Flat page background | `#f0f5fa` — a single flat colour with no depth or visual interest |
| Dense layout | Minimal vertical whitespace; cards feel cramped |
| No brand identity | Nothing visually signals "SurgMentor" — no mark, icon, or distinctive visual motif |
| No transitions | Navigation tab switches are instantaneous; no smoothing |

### Header
- Gradient card (`linear-gradient(135deg, …)`) looks like a developer banner widget, not a product hero
- Text is too small (`1.9rem`, `0.875rem`) for a premium header moment
- No sub-brand tagline with visual weight
- No icon or mark alongside the brand name
- Round-cornered floating card disconnected from page flow

### Navigation
- Tab-strip with bottom-border-trick is the archetypal admin-dashboard pattern — generic
- Active state relies on `border-bottom: none` hack (visually fragile)
- No visual separation from the header card above
- Tab labels ("Case Retrieval", "OSCE Examination", "Student Profile") read like API categories

### Cards
- Barely-visible `box-shadow: 0 2px 12px rgba(3,105,161,0.08)` — no real depth
- `border-radius: 12px` is modest; reference uses larger radii
- `padding: 24px` is tight for premium feel
- `card-title` at `0.72rem` uppercase is almost invisible — creates hierarchy confusion

### Chat Interface
- Generic chat bubble design with no visual personality
- No avatar or sender indicator
- `max-width: 75%` bubbles with `border-radius: 18px 18px 4px 18px` look off-the-shelf
- Input composer has no visual frame — textarea + button floating in card space
- No character count, no visual affordance for multi-line

### OSCE Status Bar
- Left-border accent is a developer-dashboard pattern (cf. "info callout box")
- No progress visualisation — "Step 1 / 6" is just text
- No visual state change between idle / active / complete states beyond colour shift

### Score / Results Panel
- Top blue border is the only visual accent on a plain white card
- Score content is raw markdown dumped into `.prose` — no visual hierarchy for the score number
- Panel appears at bottom of page with no clear visual moment

### Profile / Stats
- Two plain cards with small placeholder text
- No visual data representation (no charts, no metric highlights)
- "Performance Statistics" and "Personalised Study Plan" are card-titles at 0.72rem — near invisible labels
- Stats are rendered as markdown tables — functional but not premium

### Footer
- Shows raw `session: abc123de…` — developer detail in production UI
- No meaningful links, only version string

---

## 2. Reference Design Characteristics (primeiroolhar.app.br)

Primeiroolhar is a Brazilian healthcare AI platform for early autism screening. Key observations:

### Visual Language
- **Background**: Near-white (`#fafafa` range), almost imperceptible blue-grey undertone — clean without sterility
- **Cards**: Bright white surfaces with generous padding, soft rounded corners (`~16–20px`), subtle diffuse shadows
- **Color accent**: Warm, trustworthy primary — likely soft purple-blue or teal; used sparingly on CTAs and highlights
- **No heavy gradients**: The gradient, if any, is very soft on the hero area — the dominant feel is light and airy

### Typography
- **Hero headline**: Very large (2.5–3rem), heavy weight (800+), short poetic copy ("Apoio precoce, futuro brilhante") — emotionally resonant
- **Subtext**: Comfortable body size (~1rem), moderate weight, muted colour, good line-height
- **Section labels**: Small caps or spaced labels for sections with low contrast — structural, not distracting
- **Human warmth copy**: "Feito com carinho para famílias" — taglines with emotional register

### Navigation
- **Logo + name** left-anchored
- **Horizontal text links** right-anchored (not button tabs) — clean, minimal, premium
- **No heavy borders** between nav and page
- **Language toggle** as an accessible control

### Layout & Spacing
- **Generous vertical rhythm** — sections have breathing room (80–100px section gaps)
- **Centered, constrained max-width** (~960px)
- **Step-numbered flow** — large numbered circles before section titles give clear progress
- **Single prominent hero CTA** button — bold, rounded, full colour

### Components
- **Form fields**: Clean, spacious, soft borders, clear focus states
- **File upload**: Drag-and-drop zone with dashed border, icon, clear instructions
- **Privacy badge**: Trust signal with lock icon + short copy placed prominently
- **Numbered step circles**: Large (2rem+), coloured, positioned as section anchors

### Interaction Feel
- **Soft, purposeful**: Nothing jumps or flashes — smooth, calm
- **Accessible contrast**: High contrast text on light backgrounds throughout
- **Mobile-first**: Responsive, stacks cleanly on narrow viewports

---

## 3. Proposed Visual System for SurgMentor

### Color Palette
```css
/* Background layers */
--bg-page:        #f8fafc;   /* near-white, barely blue */
--bg-card:        #ffffff;
--bg-surface:     #f1f5f9;   /* pressed states, code blocks, table headers */

/* Brand blue — trustworthy, medical, strong */
--blue-900:       #1e3a5f;   /* hero gradient deep end */
--blue-700:       #1d4ed8;   /* primary interactive */
--blue-600:       #2563eb;   /* hover state */
--blue-100:       #dbeafe;   /* light tint backgrounds */
--blue-50:        #eff6ff;   /* very light surface */

/* Text */
--text-primary:   #0f172a;   /* near-black, warm */
--text-secondary: #475569;   /* medium grey */
--text-tertiary:  #94a3b8;   /* hints, labels */

/* Borders */
--border:         #e2e8f0;
--border-focus:   #3b82f6;

/* Semantic */
--success:        #059669;
--success-bg:     #ecfdf5;
--error:          #dc2626;
--error-bg:       #fef2f2;
--warning:        #d97706;

/* Shadows */
--shadow-sm:      0 1px 2px rgba(0,0,0,0.05);
--shadow-md:      0 1px 3px rgba(0,0,0,0.08), 0 8px 24px rgba(15,23,42,0.06);
--shadow-lg:      0 2px 4px rgba(0,0,0,0.06), 0 16px 40px rgba(15,23,42,0.10);
--shadow-blue:    0 4px 24px rgba(29,78,216,0.18);
```

### Typography
```css
/* Font: Inter from Google Fonts — loaded in <head> */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

--font-sans:      'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Scale */
--text-xs:    0.75rem;    /* 12px — labels, meta */
--text-sm:    0.875rem;   /* 14px — secondary body, buttons */
--text-base:  1rem;       /* 16px — primary body */
--text-lg:    1.125rem;   /* 18px — card titles */
--text-xl:    1.375rem;   /* 22px — section titles */
--text-2xl:   1.75rem;    /* 28px — hero sub */
--text-3xl:   2.375rem;   /* 38px — hero main */

/* Weights */
--weight-normal:  400;
--weight-medium:  500;
--weight-semi:    600;
--weight-bold:    700;
--weight-black:   800;
```

### Shape & Radius
```css
--radius-sm:   8px;    /* small tags, inline elements */
--radius-md:   12px;   /* buttons */
--radius-lg:   16px;   /* cards */
--radius-xl:   20px;   /* hero card, large panels */
--radius-full: 9999px; /* pills, avatars */
```

### Spacing
```css
/* 8-point grid */
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
```

---

## 4. Layout Changes

### Page Structure (current → proposed)

**Current:**
```
[container]
  [.header (gradient card)]
  [.nav (tab strip)]
  [.view (cards)]
  [.footer]
```

**Proposed:**
```
[page-bg]                     ← soft gradient page background
  [.app-header]               ← sticky/fixed topbar: logo + nav pills + session badge
  [.hero]                     ← large hero band (only shown on first load / chat view)
  [.main-content]             ← centred max-width container
    [.view.active]
  [.page-footer]
```

**Key layout changes:**
- Header becomes a proper sticky topbar with brand mark + navigation — inspired by reference's logo+links pattern
- Navigation moves into the header bar as pill buttons (not a tab strip below the header card)
- Hero section is a full-width band with the brand statement — appears as the page's "above the fold" moment
- Main content is a clean container below the hero
- Footer is simplified — no session ID exposed

### Max-width & Padding
- Container: `max-width: 860px; margin: 0 auto; padding: 0 24px`
- On mobile (`< 640px`): `padding: 0 16px`

---

## 5. Component-by-Component Redesign

### 5.1 App Header / Navigation Bar

**Current problem:** Gradient floating card + separate tab strip = two disconnected zones.

**Proposed:**
```
[header bar]  height: 64px, white bg, bottom border
  [brand]     SVG scalpel/medical mark (inline) + "SurgMentor" logotype
  [nav pills]  3 pill buttons: Case Retrieval · OSCE Exam · Profile
  [session]   subtle session badge (right side, text only, no monospace dump)
```

- Sticky top on scroll (position: sticky; top: 0; z-index: 100)
- White background with `border-bottom: 1px solid var(--border)` and subtle shadow on scroll
- Nav pills: `background: transparent` rest state, `background: var(--blue-50); color: var(--blue-700)` active state, `border-radius: var(--radius-full)`
- No border-bottom-hack — clean pill approach
- Icons before each nav label (inline SVG: stethoscope, clipboard, user)

### 5.2 Hero Section

**Current problem:** No premium hero moment — just a blue card banner.

**Proposed:**
```
[hero]  padding: 56px 24px 48px
  [eyebrow]    "Surgical Education · AI Agents"  (small caps, blue)
  [headline]   "Train Smarter. Operate Safer."  (2.375rem, weight 800)
  [subline]    "Agentic OSCE training with real surgical case retrieval,
                clinical reasoning assessment, and personalised feedback."
  [badge row]  [🔬 RAG-powered] [🏥 OSCE certified] [📊 Score tracking]
```

- Background: very subtle radial gradient from `#eff6ff` at top-centre to `#f8fafc`
- No heavy gradient card — the hero is the page itself, light and open
- `max-width: 680px` for text — maintains readable line length
- Hero only visible on the Case Retrieval and landing state; it collapses or hides on OSCE/Profile tab switches (optional: always show it as part of the fixed structure, condensed on mobile)

### 5.3 Cards

**Current problem:** 12px radius, thin shadow, 24px padding — looks minimal but not polished.

**Proposed:**
```css
.card {
  background: #fff;
  border-radius: var(--radius-lg);       /* 16px */
  border: 1px solid var(--border);
  box-shadow: var(--shadow-md);           /* layered shadow */
  padding: 28px 32px;
  margin-bottom: 20px;
}
```

- Section heading inside card: `font-size: var(--text-lg); font-weight: var(--weight-bold); color: var(--text-primary)` — no more tiny uppercase labels as primary headings
- Optional coloured top strip for differentiation (e.g., OSCE card gets a blue top stripe)
- Cards animate in on tab switch: `opacity: 0 → 1; transform: translateY(8px) → 0; transition: 0.2s`

### 5.4 Chat Interface (Case Retrieval)

**Section label:** "Case Retrieval" (larger, weighted) with subtitle "Ask about surgical cases or request cases by diagnosis"

**Composer area:**
```
[composer card]  separate sub-card with slightly different background
  [textarea]     rounded, 40px min-height, auto-resize
  [send btn]     right side, icon + "Send"
  [hint]         below textarea: "Press Enter to send · Shift+Enter for new line"
```

**Message bubbles — redesigned:**
```
User bubble:
  background: linear-gradient(135deg, #1d4ed8, #2563eb)
  color: #fff
  border-radius: 20px 20px 4px 20px
  padding: 12px 16px
  box-shadow: 0 2px 8px rgba(29,78,216,0.25)
  max-width: 78%

Assistant bubble:
  background: #fff
  border: 1px solid var(--border)
  border-radius: 4px 20px 20px 20px
  padding: 14px 18px
  box-shadow: var(--shadow-sm)
  max-width: 85%
```

**Avatar dots:**
- User: small 28px circle, blue background, "You" initial or stethoscope icon
- Assistant: small 28px circle, white + blue border, "S" for SurgMentor

**Typing indicator:** Retain current 3-dot bounce, but in a proper assistant bubble frame

**Markdown rendering:** Assistant bubbles render HTML (current behaviour preserved)

**Action row:**
- "↺ Clear Session" → "New Conversation" with bin icon, placed below composer

### 5.5 OSCE Status / Progress Component

**Current problem:** Left-border callout box looks like a code editor info panel.

**Proposed — OSCE Step Progress Bar:**
```
[osce-progress]
  [status pill]     "● Active" / "○ Not started" / "✓ Complete"  (pill badge)
  [step track]      visual stepper: ●—●—●—○—○—○  (step dots + connecting line)
  [step label]      "Step 3 of 6 — Examination Findings"
```

CSS approach:
```css
.osce-progress {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 24px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 20px;
  box-shadow: var(--shadow-sm);
}
.step-track { display: flex; align-items: center; gap: 6px; }
.step-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--border);          /* inactive */
  transition: background 0.3s;
}
.step-dot.done   { background: var(--blue-700); }
.step-dot.active { background: var(--blue-600); box-shadow: 0 0 0 3px var(--blue-100); }
/* connecting line via flex gap with ::after pseudo-elements */
```

The step count changes live as `osce_step` updates — the JS already has this data. This is purely a visual upgrade of the existing `setOsceUI()` function call.

### 5.6 OSCE Action Buttons

**Current:** Three flat buttons in a row with icon glyphs (▶ ⏹ ↺)

**Proposed:**
```
[Start Session]   btn-primary, large, SVG play icon, full blue
[End & Score]     btn-warning (amber), SVG stop icon, appears when active
[New Session]     btn-ghost (outline), SVG refresh icon
```

Button sizing: `padding: 12px 22px; font-size: 0.9375rem; border-radius: var(--radius-md)`

### 5.7 Score / Results Panel

**Current problem:** Plain white card with blue top border; raw markdown dump.

**Proposed:**
```
[score-panel]
  [score-header]   gradient blue band: "Session Complete" + score badge
    [score-number] large "8 / 10" display (extracted from markdown or shown as-is)
  [score-body]     white card below: rendered markdown (feedback text)
  [action]         "Start New Session" button
```

CSS:
```css
.score-panel {
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--blue-100);
  margin-top: 20px;
}
.score-header {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 100%);
  padding: 24px 32px;
  color: #fff;
}
.score-body {
  background: #fff;
  padding: 24px 32px;
}
```

Note: The score number is already in the markdown response as `## OSCE Score: X/10`. No parsing change needed — the `.prose` CSS will give it good hierarchy. The header just sets context.

### 5.8 Profile / Statistics View

**Current problem:** Two plain cards with small text and placeholder italic copy.

**Proposed:**

**Statistics card:**
```
[stats-card]
  [heading]      "Your Performance"
  [lead-copy]    "Complete OSCE sessions to build your profile."
  [stats-grid]   2×2 or 3-column metric tiles (if data available):
                   [Sessions completed]  [Average score]  [Weak areas]
  [full-stats]   Full markdown content below metrics (existing .prose render)
  [refresh btn]  "↻ Refresh" — icon only or text, secondary style
```

**Study Plan card:**
```
[plan-card]
  [heading]      "Study Plan"
  [lead-copy]    "AI-generated recommendations based on your performance."
  [plan-content] rendered markdown (existing .prose)
  [generate btn] "Generate Study Plan" — primary, full width or prominent
```

The metric tiles are pure CSS — they parse nothing new from the backend; they only show when the stats markdown is successfully loaded (a class toggle). They serve as a visual frame for the markdown content below.

### 5.9 Buttons

**Proposed button system:**
```css
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);       /* 12px */
  font-size: var(--text-sm);            /* 14px */
  font-weight: var(--weight-semi);      /* 600 */
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.btn-primary {
  background: var(--blue-700);
  color: #fff;
  box-shadow: 0 1px 2px rgba(29,78,216,0.2), 0 2px 8px rgba(29,78,216,0.12);
}
.btn-primary:hover:not(:disabled) {
  background: var(--blue-600);
  box-shadow: 0 2px 4px rgba(29,78,216,0.25), 0 4px 16px rgba(29,78,216,0.18);
  transform: translateY(-1px);
}

.btn-secondary {
  background: #fff;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}
.btn-secondary:hover:not(:disabled) {
  border-color: var(--blue-700);
  color: var(--blue-700);
  background: var(--blue-50);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
}
.btn-ghost:hover:not(:disabled) {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none !important; }
```

Large variant (`.btn-lg`): `padding: 13px 26px; font-size: var(--text-base)`  
Small variant (`.btn-sm`): `padding: 7px 14px; font-size: var(--text-xs)`

### 5.10 Input / Textarea

```css
textarea, input[type=text] {
  border-radius: var(--radius-md);      /* 12px */
  border: 1.5px solid var(--border);
  padding: 12px 16px;
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  color: var(--text-primary);
  background: #fff;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.04);
  transition: border-color 0.15s, box-shadow 0.15s;
  width: 100%;
}
textarea:focus, input[type=text]:focus {
  outline: none;
  border-color: var(--blue-700);
  box-shadow: 0 0 0 3px rgba(29,78,216,0.10), inset 0 1px 2px rgba(0,0,0,0.04);
}
```

The composer area gets a containing `div.composer` with `background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border); padding: 12px 14px` — giving it a "slot" feel rather than a floating textarea.

### 5.11 Inline Status / Error Messages

```css
.inline-msg {
  display: flex; align-items: center; gap: 8px;
  font-size: var(--text-sm);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  margin-top: 12px;
}
.inline-msg.error {
  background: var(--error-bg);
  color: var(--error);
  border: 1px solid #fca5a5;
}
.inline-msg.info {
  background: var(--blue-50);
  color: var(--blue-700);
  border: 1px solid var(--blue-100);
}
```

### 5.12 Footer

```
[footer]
  SurgMentor v1.0  ·  Kaggle AI Agents Intensive 2026
  [no raw session ID exposed]
```

---

## 6. Icons

All icons are **inline SVG paths** — no external icon library, no font icons, no paid assets. Inline SVGs are zero-dependency and render at any size.

Proposed icons (simple, single-path, healthcare-appropriate):

| Location | Icon | SVG description |
|---|---|---|
| Header brand | Scalpel/caduceus | Simplified scalpel shape |
| Nav: Case Retrieval | Stethoscope | Simple stethoscope |
| Nav: OSCE | Clipboard/checklist | Clipboard with tick |
| Nav: Profile | User outline | Head+shoulders silhouette |
| Start Session btn | Play triangle | Solid right-pointing triangle |
| End & Score btn | Square stop | Solid square |
| New Session btn | Refresh arrows | Two circular arrows |
| Send btn | Arrow right | Right-pointing arrow |
| Stats refresh | Refresh | Circular arrow |
| Score complete | Medal / check | Circle with checkmark |

---

## 7. Animations & Transitions

All animations are `prefers-reduced-motion` aware (`@media (prefers-reduced-motion: reduce) { * { animation: none; transition: none; } }`).

| Interaction | Effect |
|---|---|
| Tab switch | Fade + 6px translateY, 180ms ease-out |
| Message appear | Fade in + 4px translateY, 150ms ease (existing `fadeIn` — kept) |
| Button hover | `transform: translateY(-1px)`, box-shadow increase, 150ms |
| Card entry | Stagger fade on first view load (optional) |
| Score panel reveal | Slide down from above fold with fade, 250ms |
| OSCE step update | Step dot background transitions, 300ms |
| Typing dots | Bounce (existing — kept) |

---

## 8. Responsive Behaviour

### Breakpoints
- `640px`: Mobile — primary breakpoint
- `768px`: Tablet

### Changes at ≤640px
- Header: logo + hamburger or auto-collapse nav pills to icon-only
- Nav: pills stack below brand (2-row header) OR reduce to icon-only labels
- Hero: smaller heading (1.75rem), remove badge row
- Cards: padding reduces to `20px`
- Chat messages: `max-height: 320px` (reduce from 480px)
- Buttons: full-width in column layout where appropriate
- OSCE step track: reduced to 6 small dots only (no connecting line text)
- Footer: centred, single column

### Changes at 641–768px (tablet)
- Container stays at full width with 24px padding
- Nav pills still fit in one row
- Cards at normal padding

---

## 9. Accessibility Considerations

| Concern | Solution |
|---|---|
| Focus states | All interactive elements get visible `outline: 2px solid var(--blue-600); outline-offset: 2px` focus ring |
| Colour contrast | Primary text on white: 16:1. Blue on white buttons: checked ≥4.5:1 |
| Button size | All buttons ≥44px touch target height |
| ARIA | Nav buttons get `role="tab"` + `aria-selected`; views get `role="tabpanel"` |
| Live regions | Chat message container gets `aria-live="polite"` so screen readers announce new messages |
| Semantic HTML | `<nav>`, `<main>`, `<header>`, `<footer>` elements |
| Icon-only buttons | `aria-label` attributes on icon-only controls |

---

## 10. Exact Files to Modify

| File | Change type |
|---|---|
| `web/index.html` | Full CSS + HTML structure redesign; JS logic unchanged |

No other files change. All backend, tests, skills, and server files are untouched.

---

## 11. Visual Changes vs Functional Changes

### Visual changes only (no JS or API changes)

- Color palette update (CSS custom properties)
- Font loading (Google Fonts `<link>` in `<head>`)
- Header restructure: gradient card → sticky topbar
- Navigation: tab strip → pill buttons inside header
- Hero section: new HTML band below header
- Card radius, shadow, padding increases
- Button style system overhaul
- Chat bubble redesign (CSS only)
- OSCE step progress bar (CSS + minor HTML additions to the status div)
- Score panel header band (HTML structure around existing `#score-panel`)
- Profile metric tiles (HTML structure + CSS; no new JS)
- Input/composer framing (wrapping HTML div, CSS)
- Icon SVGs inserted inline (HTML)
- Footer simplification (remove session ID display from footer — keep in hidden element for debugging)
- Animation/transition updates
- Responsive CSS additions

### Functional changes (minimal, non-breaking)

| What | Why | Risk |
|---|---|---|
| `setOsceUI()` must also update step dots | The OSCE progress bar needs step count | **Low** — adds 6 lines to existing function |
| Session ID removed from footer display | UX cleanliness | **None** — session ID still lives in `sessionId` JS variable; the `#footer-session` element can be hidden with CSS or removed from the footer but kept as a hidden `<span data-debug>` |
| `appendMsg()` gets avatar wrapper HTML | Avatar dots on chat bubbles | **Low** — only changes the DOM structure of message bubbles, not the logic |
| Tab switch adds CSS transition class | Smooth fade | **None** — `showView()` gets one extra class toggle |

### No changes to
- `apiPost()` / `apiGet()` — identical
- `sessionId` management — identical
- `chatSend()` / `chatClear()` — identical
- `osceStart()` / `osceSend()` / `osceFinish()` / `osceReset()` — identical
- `profileRefresh()` / `profilePlan()` — identical
- `renderMd()` / `escHtml()` — identical
- `autoResize()` — identical
- All keyboard event handlers — identical
- All API endpoint calls and response parsing — identical
- `sessionStorage` usage — identical

---

## 12. Risks to Existing JavaScript Functionality

| Risk | Severity | Mitigation |
|---|---|---|
| Element IDs renamed by accident | High | Plan preserves all existing IDs: `chat-messages`, `chat-input`, `chat-send-btn`, `chat-error`, `osce-status`, `osce-messages`, `osce-input`, `osce-input-row`, `osce-send-btn`, `osce-error`, `osce-start-btn`, `osce-finish-btn`, `osce-reset-btn`, `score-panel`, `score-content`, `stats-content`, `stats-error`, `stats-refresh-btn`, `plan-content`, `plan-error`, `plan-btn`, `footer-session`, `view-chat`, `view-osce`, `view-profile` |
| `.hidden` class still toggles visibility | Medium | CSS preserves `.hidden { display: none !important; }` |
| `.nav-btn.active` toggles break | Low | New pill nav keeps `nav-btn` + `active` class names |
| `showView()` breaks on renamed view IDs | Low | View IDs `view-chat`, `view-osce`, `view-profile` unchanged |
| Score panel `.visible` class | Low | `.score-panel.visible` kept; only wrapping HTML changes |
| `typing-dots` class referenced in `appendLoading()` | Low | Class name kept; only outer bubble style changes |
| `osce-status` class + `active` modifier | Low | Class names preserved; visual style changes only |

---

## 13. Implementation Sequence (for reference — not executing yet)

1. Update `<head>`: add Google Fonts `<link>`, update `<title>`
2. Replace CSS custom properties block (design system)
3. Add global reset + base styles
4. Rewrite header HTML (`<header class="app-header">`)
5. Add hero section HTML (visible only on initial state)
6. Rewrite `.nav` HTML (pill buttons inside header)
7. Update card CSS
8. Update button CSS system
9. Update textarea / composer CSS + wrapper div
10. Update chat bubble CSS
11. Update OSCE progress component HTML + CSS
12. Update score panel HTML wrapper + CSS
13. Update profile view HTML layout
14. Add icon SVGs
15. Add animation CSS
16. Add responsive CSS
17. Add accessibility attributes
18. Update `setOsceUI()` for step dots (6 lines)
19. Update `appendMsg()` for avatar wrappers
20. Add tab switch fade to `showView()`
21. Smoke-test all 10 functions

---

## Summary

The redesign converts SurgMentor from a developer-demo aesthetic into a premium healthcare product interface, drawing on the clean, calm, trustworthy character of the reference site. It is a **pure frontend change** — every existing API call, session management pattern, and JavaScript function is preserved with identical logic. The only JS changes are cosmetic additions to three functions (`setOsceUI`, `appendMsg`, `showView`) that drive new visual components without altering data flow.

All work is confined to `web/index.html`.
