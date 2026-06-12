---
hash: "8a8f6fa7"
id: "a91a6a3e"
read_when: "building or debugging anything that runs `claude -p` headlessly — especially eval harnesses that need a clean-room agent isolated from this repo's skills/CLAUDE.md/hooks; also a reference for the headless CLI flags and JSON output envelope"
summary: "Reference for running headless `claude -p` in an isolated clean room: how auth, config-dir relocation, skill discovery, and context inheritance actually behave, the isolation recipe for eval arms, the relevant CLI flags, the JSON output shape, and the non-obvious gotchas. Verified empirically against Claude Code 2.1.175."
title: "Headless Claude CLI for Evals (isolation, flags, output)"
---

# Headless Claude CLI for Evals

Reference for driving `claude -p` (Claude Code headless) as an eval runner that must produce a **clean room** — an agent that sees none of this repo's content (project `CLAUDE.md`, installed skills, memory, hooks, MCP) except optionally one skill-under-test. Verified empirically against **Claude Code 2.1.175**; see `assurance-eval-isolation-spike.md` (task 001) for the run evidence. Findings are version-sensitive — re-verify the two conditions below if the CLI version moves a lot.

## Why isolation matters

For a with-skill-vs-without-skill eval, the baseline ("without skill") arm is only meaningful if the agent does **not** inherit the repo's own skills/CLAUDE.md. The two arms must be byte-identical except for the one skill being measured, so any output difference is attributable to that skill.

## Auth

- Auth in this environment is a **file**: `~/.claude/.credentials.json` (mode 600). There is **no** `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` in the env.
- A relocated config dir (`CLAUDE_CONFIG_DIR`) containing **only** a copy of `.credentials.json` authenticates fine — nothing else is needed for auth.
- Token refreshes write back to the *relocated* dir, so isolation is preserved across a run.
- A runner should **fail fast** if the source credentials file is absent rather than producing a confusing auth error mid-run.

## The isolation recipe

Per run, outside the repo tree:

```bash
BASE=$(mktemp -d)            # MUST be outside the repo (see Gotcha 1)
CFG="$BASE/config"; WS="$BASE/ws"
mkdir -p "$CFG" "$WS"
cp ~/.claude/.credentials.json "$CFG/.credentials.json"

# with-skill arm only — drop the compiled skill into the relocated home:
#   $CFG/skills/<skill-name>/SKILL.md  (+ references/)
# baseline arm = identical, minus that directory.

cp -r <fixture>/* "$WS"/     # the target repo the agent works in

( cd "$WS" && CLAUDE_CONFIG_DIR="$CFG" claude -p "$PROMPT" \
    --output-format json \
    --strict-mcp-config \
    --permission-mode bypassPermissions \
    --model <pinned-model> \
    < /dev/null > out.json 2> err.txt )
```

The two arms differ by exactly one skill directory → the output diff is attributable to that skill.

## Two non-obvious conditions (both required)

1. **The workspace (cwd) must be OUTSIDE the repo tree.** Claude Code walks *up* from cwd and re-discovers a parent repo's project skills **and** `CLAUDE.md` — *regardless* of `CLAUDE_CONFIG_DIR`. Running in `.tmp/` (under the repo root) leaks all the repo's project skills + CLAUDE.md back in. Use `mktemp -d`; never `.tmp/`.
2. **Do NOT pass `--setting-sources ''`.** It does isolate (zero skills, no CLAUDE.md) — but it *also* suppresses discovery of the skill-under-test, silently breaking the with-skill arm. Omit it; isolation comes from the clean config dir + out-of-repo cwd instead. Default sources are correct: the `user` source reads the (clean) `CLAUDE_CONFIG_DIR`, and `project`/`local` read cwd (the fixture) — so a fixture that legitimately ships its own `.claude/`/CLAUDE.md WILL load, which is usually what you want.

## Skill discovery

- Personal-skill discovery path: **`$CLAUDE_CONFIG_DIR/skills/<name>/SKILL.md`** (mirrors `~/.claude/skills/<name>/SKILL.md`). A skill dropped there loads as exactly one extra entry.
- Confirmed by injecting a uniquely-named marker skill: baseline showed N skills, with-skill showed N+1, the extra being the marker (a name the agent could only know by discovery — so the agent's self-report of available skills is real, not hallucinated).

## The irreducible floor (~14 built-in commands)

These ship with the `claude` **binary**, not the config dir, so `CLAUDE_CONFIG_DIR` cannot remove them; they appear in **both** arms:

`init`, `review`, `security-review`, `verify`, `run`, `code-review`, `simplify`, `deep-research`, `loop`, `schedule`, `update-config`, `keybindings-help`, `claude-api`, `fewer-permission-prompts`

- A truly *zero-skill* baseline is **not** achievable without disabling the Skill/SlashCommand tooling wholesale (which would also remove the skill-under-test) — not worth it.
- Harmless to the differential (constant across arms). A few are assurance-adjacent (`verify`, `code-review`, `run`, `simplify`) but are slash commands the agent won't auto-invoke for an ordinary build prompt. Note them in eval reports for honesty; don't fight them.

## Isolation-relevant flags (Claude Code 2.1.175)

| Flag | Use |
|---|---|
| `-p, --print` | Headless: print response and exit. |
| `--output-format <text\|json\|stream-json>` | `json` returns a structured envelope (see below). |
| `--strict-mcp-config` | Only use MCP from `--mcp-config`; ignore all other MCP. With no `--mcp-config` → zero MCP servers. |
| `--permission-mode <mode>` | `bypassPermissions` (or `acceptEdits`) so a headless run doesn't hang on prompts. |
| `--setting-sources <user,project,local>` | Which settings sources load. **Avoid `''`** (kills skill-under-test). |
| `--add-dir <dirs...>` | Extra allowed dirs — **also loads their CLAUDE.md**; don't point at the repo. |
| `--system-prompt` / `--append-system-prompt` | Replace vs append the system prompt. |
| `--exclude-dynamic-system-prompt-sections` | Moves cwd/env/memory/git-status out of the system prompt (determinism / cache reuse). Default prompt only. |
| `--mcp-config <files...>` | Explicit MCP servers (pair with `--strict-mcp-config`). |
| `--model <id>` | **Pin it** for reproducible scorecards (see Gotcha 3). |

`CLAUDE_CONFIG_DIR` (env, not a flag) relocates the `~/.claude` home — the keystone isolation lever.

## JSON output envelope (`--output-format json`)

Fields observed on the top-level object:

- `result` — **the final assistant message text only.** Earlier turns (e.g. tool calls and their narration) are NOT in `result`. → If you want a structured report, instruct the agent to emit it as its **final** message; otherwise it gets buried behind tool output.
- `num_turns`, `session_id`, `total_cost_usd`.
- `modelUsage` — per-model token + cost breakdown (keyed by model id).

Parse with `jq -r '.result'`; keep the whole JSON as the run's evidence artifact.

## Gotchas

1. **cwd walk-up leaks project context** — the biggest trap. (See condition 1.) The intuitive `.tmp/` location is exactly wrong for the eval workspace.
2. **`.result` is final-message-only** — put any structured probe/report last, or it won't appear.
3. **Model mixing** — default `claude -p` uses a *mix* (Haiku for trivial turns, the session model for the main turn). Pin `--model` for reproducible cost/quality scorecards.
4. **stdin** — headless runs warn `no stdin data received in 3s`; redirect `< /dev/null` to skip the wait.
5. **`--setting-sources ''` is a trap** — strongest-looking lever, silently disables the skill-under-test. (See condition 2.)
6. **Local hooks can block your harness commands** — e.g. a `PreToolUse` Bash hook (`dcg`) in the *parent* session blocks `rm -rf`; use `mktemp -d` + leave temp dirs for the OS to reap rather than scripting destructive cleanup.
