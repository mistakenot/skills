# Replay fixture candidates (auto-stack)

Mined from `~/src/auto-stack` git history (no GitHub). Selection criteria: a **separate
`docs(tasks): add task NNN` commit** (so the planning docs are pure ground truth, isolated
from implementation), a **clean parent SHA** (pre-task checkout, no impl leakage), a
**retrievable planning session**, and a **modest size**.

## Recommended

| Task | start_sha (parent of docs commit) | Docs | Planning session | Notes |
|------|-----------------------------------|------|------------------|-------|
| **008-commit-session-link** | `0ea36adc43943dea77a2d6b66fad161d4558ced4` | 4 files, +470 | `a5c7f4c0-c0ba-43c8-a6a0-3713f6c17f62` (confirmed: full new-task→solution→plan + genuine human turns) | **Best first fixture.** Small, self-contained (git pre-commit hook for commit↔session trailers). |
| 010-autosearch-co-change | `a78aa5c3f166ae935b91622dab1034bb4419a43d` | 4 files, +546 | sessions in window (2026-05-28..31) | Medium; co-change search feature. |
| 015-session-intent-summary | `cbef52313c8fa22ce086cd99515506607e5e5f5a` | 4 files, +506 | sessions in window (2026-06-07..10) | Medium. |
| 028-bus-event-host-field | `927c2b638a8c8fadd4a8830bc7a3dfc7d5cea004` | 2 files, +442 | candidates incl. `d278273a…` | Uses **plan.html** (newer format) — good to exercise the html workflow too. |

## Rejected

- **004-context-pack, 007-autograph-doc-links** — docs squashed *with* implementation in one
  `feat(...)` commit (spike S2 case); contamination-prone, harder to get a clean start state.
- **020-auto-hooks-install, 022-hook-event-log** — **no indexed sessions** on 2026-06-11
  (index gap); can't recover the human turns.

## Caveats found while mining

- The top *content* search hit for a task is often the **execution** session (coordinator +
  teammate messages), not planning. Pinpoint the planning session by the `/new-task`,
  `/new-solution`, `/new-plan` flow + genuine human requirement-giving turns.
- Some tasks were planned across **multiple sessions** that reference already-existing docs
  ("read task docs… bring yourself up to speed"). Fine for hand-authored scripts; a
  complication for later auto-extraction.
- Genuine human turns must be filtered from injected boilerplate: `<local-command…>`,
  `<command-name>…`, "Base directory for this skill", and `<teammate-message>` blocks.
