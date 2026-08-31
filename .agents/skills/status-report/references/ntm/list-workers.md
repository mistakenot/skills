# Listing workers and identifying their agent type

Enumerate every pane in an `ntm` session and work out which coding-agent CLI (if
any) occupies each one.

## Find a session to enumerate

```bash
ntm list --json
```

Each entry under `.sessions[]` has a `.name` and an `.agents` breakdown that
counts every supported type — including `opencode`:

```json
{ "name": "myproj", "pane_count": 4,
  "agents": { "claude": 1, "codex": 1, "opencode": 1, "user": 1, "total": 4 } }
```

Use `.agents` to pick a session that actually has the agent type you want
before enumerating its panes below.

## Enumerate panes

```bash
ntm status <session> --json
```

`.panes[]` is the authoritative list. Each pane carries everything needed to
target it:

| Field       | Meaning                          | Example values                          |
| ----------- | --------------------------------- | ---------------------------------------- |
| `.index`    | Pane number — use this to target | `0`, `1`, `2`, `3`                       |
| `.type`     | Agent type (canonical)           | `claude`, `codex`, `oc`, `user`         |
| `.command`  | Process running in the pane      | `claude`, `node` (codex), `opencode`    |
| `.title`    | Tmux pane title                  | `✳ Claude Code`, `myproj__cod_1`, `myproj__oc_1` |

Each pane entry also carries context-usage fields: `context_tokens`,
`context_limit`, `context_percent`, and `context_model`. `context_percent` is
used to detect context exhaustion (95%+ = stuck). Source:
`src/planning-workflow/skills/status-report/SKILL.md:43`, written from real
use of `ntm status --json` — not re-verified live for this write-up, since
there were no running ntm sessions to check against at the time (`ntm list
--json` → `count: 0`). Re-confirm the exact field names against a live session
if precision matters.

## Identify which coding agent is in a pane

Two fields identify the agent; use them together, because **neither is
reliable alone**:

- `.command` — the live process: `claude` → **Claude Code**, `opencode` →
  **OpenCode**, `node` → **Codex** (Codex runs under Node, so `node` is its
  tell *within an ntm session*).
- `.type` — a label ntm derives from the pane **title**: `claude`, `codex`,
  `oc` (the per-pane value is `oc`, while `ntm list`'s aggregate key is
  `opencode` — same thing), or `user` for a plain shell.

**`.type` is title-derived and both lags and goes stale — do not trust it
alone (this is verified behaviour):**

- On spawn, an **OpenCode** pane can report `type: "user"` for many seconds
  (its title is `OpenCode`, not `<session>__oc_1`) and only flips to `oc` after
  the agent first produces output. Resolving OpenCode by `type=="oc"` right
  after spawn finds nothing.
- After an agent **exits** (e.g. Codex drops back to a shell), the pane keeps
  its old `type` from the stale title while `.command` already reads `bash`.

**Reliable resolution:** key off `.command` for liveness and identity —
`command=="claude"` / `command=="opencode"`, and Codex by `command=="node"`
(or `type=="codex"`, which is stable for Codex because its title is
`<session>__cod_1`). A pane whose `.command` is `bash`/a shell is **not** a
running agent regardless of `.type` — never delegate there.
