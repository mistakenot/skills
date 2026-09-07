---
hash: "49792815"
id: "a91a6a3e"
read_when: "building or debugging anything that runs `claude -p` headlessly — especially eval harnesses that need a clean-room agent isolated from this repo's skills/CLAUDE.md/hooks; also a reference for the headless CLI flags and JSON output envelope"
summary: "Reference for running headless `claude -p` in an isolated clean room: how auth, config-dir relocation, skill discovery, and context inheritance actually behave, the isolation recipe for eval arms, the relevant CLI flags, the JSON output shape, and the non-obvious gotchas. Verified empirically against Claude Code 2.1.260."
title: "Headless Claude CLI for Evals (isolation, flags, output)"
---

# Headless Claude CLI for Evals

Reference for driving `claude -p` (Claude Code headless) as an eval runner that must produce a **clean room** — an agent that sees none of this repo's content (project `CLAUDE.md`, installed skills, memory, hooks, MCP) except optionally one skill-under-test. Verified empirically against **Claude Code 2.1.260** (re-verified 2026-09-04; originally 2.1.175). See `assurance-eval-isolation-spike.md` (task 001) for the original run evidence. Findings are version-sensitive — re-verify the two conditions below if the CLI version moves a lot.

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
BASE=$(mktemp -d)            # MUST be outside the repo (see Gotcha 1), and no
                             # CLAUDE.md/.claude in ANY ancestor (Gotcha 7)
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

### Re-verification log

| CLI version | Date | Condition 1 (out-of-repo cwd isolates) | Condition 2 (default setting-sources still discovers skill-under-test) |
|---|---|---|---|
| 2.1.175 | task 001 | holds | holds |
| 2.1.260 | 2026-09-04 | holds | holds |

Condition 1 "holds" means the *repo* does not leak. It does not mean the clean
room is unconditionally clean: on the same date the walk-up was found to be
name-based, so an out-of-repo cwd still inherits any `CLAUDE.md` above it.
Canary 4 in `src/evals/canaries.py` closes that.

The 2.1.260 pass used three probes, each a single `claude -p` asking the agent to
print its cwd, list every skill it can see, and say whether it received any
project instructions:

1. **Negative control** — clean `CLAUDE_CONFIG_DIR`, but cwd *inside* the repo
   (`.tmp/probe1`): leaked all 38 repo skills **and** quoted this repo's
   `CLAUDE.md`. Condition 1's failure mode is real and the probe is sensitive.
2. **Clean room** — same config dir, cwd from `mktemp -d`: 13 skills (the
   built-in floor), no repo skills, no project instructions.
3. **Clean room + one skill** at `$CFG/skills/rich-doc/`: the same 13 plus
   exactly `rich-doc`.

A fourth probe re-checked condition 2's trap: adding `--setting-sources ''` to
probe 3 — identical config dir and cwd — dropped `rich-doc` from the list. The
flag still silently disables the skill-under-test.

## Two non-obvious conditions (both required)

1. **The workspace (cwd) must be OUTSIDE the repo tree.** Claude Code walks *up* from cwd and re-discovers a parent repo's project skills **and** `CLAUDE.md` — *regardless* of `CLAUDE_CONFIG_DIR`. Running in `.tmp/` (under the repo root) leaks all the repo's project skills + CLAUDE.md back in. Use `mktemp -d`; never `.tmp/`. And an out-of-repo cwd is necessary but not sufficient — see the walk-up section below: the CLI's project-root detection is name-based, so a `CLAUDE.md` in a non-repo ancestor such as `/tmp` leaks too.
2. **Do NOT pass `--setting-sources ''`.** It does isolate (zero skills, no CLAUDE.md) — but it *also* suppresses discovery of the skill-under-test, silently breaking the with-skill arm. Omit it; isolation comes from the clean config dir + out-of-repo cwd instead. Default sources are correct: the `user` source reads the (clean) `CLAUDE_CONFIG_DIR`, and `project`/`local` read cwd (the fixture) — so a fixture that legitimately ships its own `.claude/`/CLAUDE.md WILL load, which is usually what you want.

## The project-root walk-up is name-based (measured, 2.1.260, 2026-09-04)

**The CLI's walk-up and git's own repo test are different rules, and the CLI's is
laxer.** This machine has an empty `/tmp/.git` directory that git rejects
(`git -C /tmp rev-parse` → "not a repository"). Claude Code accepts it.

Evidence, from a clean-room cell whose cwd was
`/tmp/claude-1002/<...>/scratchpad/p2/evals-1lcuf3lm/ws` — seven levels below
`/tmp`, with no `.git` at any level in between:

```
"cwd":          ".../p2/evals-1lcuf3lm/ws"
"memory_paths": {"auto": ".../config/projects/-tmp/memory/"}
```

The project slug is `-tmp`. The CLI walked up seven directories, stopped at
`/tmp`, and resolved it as the project root on the strength of the `.git` **name**
alone.

**A `CLAUDE.md` anywhere on that path is loaded into the clean room.** Probed
directly, twice, with distinct nonsense tokens:

| Marker at | Reached the agent? | How it was presented |
|---|---|---|
| `/tmp/CLAUDE.md` | yes | "Contents of /tmp/CLAUDE.md (project instructions, checked into the codebase)" |
| `.../scratchpad/p2/CLAUDE.md` (5 levels above cwd, no `.git`) | yes | quoted verbatim as project instructions |

Both markers were removed immediately after the probe.

So the leak is not limited to the directory holding the `.git`: every directory
between cwd and the resolved project root is scanned. Consequences:

- **`mktemp -d` under `/tmp` is still usable, but not self-evidently safe.** Its
  safety rests on `/tmp` and every intermediate directory happening to contain no
  `CLAUDE.md`/`.claude`. `/tmp` is world-writable, so any process can change that
  at any time, and the contamination is silent.
- **A git-content-based check cannot catch this**, because the offending ancestor
  need not be a real repo — `/tmp` is not one.
- `src/evals/canaries.py` therefore asserts, on every cell, that no `CLAUDE.md`
  or `.claude/` exists in **any** strict ancestor of the workspace, regardless of
  git status (canary 4). Strict ancestors only: a fixture's own workspace
  `CLAUDE.md` is legitimate and loads on purpose.

## Skill discovery

- Personal-skill discovery path: **`$CLAUDE_CONFIG_DIR/skills/<name>/SKILL.md`** (mirrors `~/.claude/skills/<name>/SKILL.md`). A skill dropped there loads as exactly one extra entry.
- Confirmed by injecting a uniquely-named marker skill: baseline showed N skills, with-skill showed N+1, the extra being the marker (a name the agent could only know by discovery — so the agent's self-report of available skills is real, not hallucinated).

## The irreducible floor (measure it, never hard-code it)

These ship with the `claude` **binary**, not the config dir, so `CLAUDE_CONFIG_DIR` cannot
remove them; they appear in **both** arms.

**Measure the floor from the `system/init` event in `--output-format stream-json`.** Do not
ask the agent to list its skills. On 2026-09-04 the two methods were run against the *same*
CLI version (2.1.260) and disagreed materially:

| Method | Count | Notably included | Notably missing |
|---|---|---|---|
| Agent self-report (probe prompt) | 13 | `init`, `security-review`, `keybindings-help` | `deep-research`, `verify`, `debug` |
| `system/init` event (machine-emitted) | 17 | `deep-research`, `verify`, `debug`, `batch`, `doctor` | `init`, `security-review`, `keybindings-help` |

The init-event list observed on 2.1.260: `batch`, `claude-api`, `code-review`, `dataviz`,
`debug`, `deep-research`, `design-sync`, `doctor`, `fewer-permission-prompts`, `loop`, `run`,
`run-skill-generator`, `schedule`, `simplify`, `update-config`, `verify`, `workflow-authoring`.

**Assert against the init event, not a self-report.** The model is not hallucinating — the
reconciliation below shows both lists are real, with different inclusion rules — but a
self-report is the model describing its own context in prose, and it is neither complete nor
stably shaped. `init.skills` is machine-emitted and is the right assertion target, read as
"skills the runtime registered" rather than as a complete inventory.

### The discrepancy is not environmental (reconciled 2026-09-04)

Execution context was the leading suspect — the two 2.1.260 measurements were
originally taken in different ones. It is not the cause. A single cell was asked
to list its skills, and its **own** `system/init` event was read from the same
`stream.jsonl`: same process, same run, same environment. They still disagreed,
with exactly the membership delta reported above.

| | Count (floor, excluding the installed skill) | |
|---|---|---|
| `system/init` `skills` array | 17 | ground truth for the arm-vs-arm differential |
| Agent self-report, same run | 13 | adds `init`, `security-review`, `keybindings-help`; omits `deep-research`, `verify`, `debug`, `batch`, `doctor`, `design-sync`, `run-skill-generator` |

The cause is that these are two different views with different inclusion rules,
not two measurements of one list:

- The init event's `skills` array omits `init`, `security-review` and
  `keybindings-help` — yet `init` and `security-review` appear in that same
  event's `slash_commands` array, and all three are real built-ins. The
  self-report is not hallucinating them.
- The entries the model omits (`deep-research`, `verify`, `debug`, `batch`,
  `doctor`, …) are user-invocable commands, the shape `disable-model-invocation`
  produces: registered, listed by init, not offered to the model.

**Neither list is a complete inventory of what the binary ships.** `init.skills`
is still the right thing to assert on — it is machine-emitted, stable within a
run, and identical across a run's arms — but read it as "skills the runtime
registered", not "everything the agent can see".

The 17-entry init list above was re-confirmed against three fresh 2.1.260 cells
on 2026-09-04: identical membership every time.

**The floor still varies by environment, not only by CLI version.** So:

- never hard-code the list, or a count, as a cleanliness assertion;
- assert on the **config directory contents**, which you control;
- if a run needs the visible list, read it from the init event and compare **arms against each
  other within that run**, never against a constant.

Assume constancy only *within* a single run's arms — which is all the differential needs.

- A truly *zero-skill* baseline is **not** achievable without disabling the Skill/SlashCommand
  tooling wholesale (which would also remove the skill-under-test) — not worth it.
- Harmless to the differential (constant across arms). A few are assurance-adjacent (`verify`,
  `code-review`, `run`, `simplify`) but are slash commands the agent won't auto-invoke for an
  ordinary build prompt. Note them in eval reports for honesty; don't fight them.

## Isolation-relevant flags (Claude Code 2.1.260)

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
6. **A `CLAUDE.md` in a non-repo ancestor still leaks** — project-root detection is name-based, so `/tmp/.git` (which git itself rejects) makes `/tmp` a project root and `/tmp/CLAUDE.md` project instructions. A content-based git check will not catch it; assert on the filenames in every ancestor.
7. **Local hooks can block your harness commands** — e.g. a `PreToolUse` Bash hook (`dcg`) in the *parent* session blocks `rm -rf`; use `mktemp -d` + leave temp dirs for the OS to reap rather than scripting destructive cleanup.
