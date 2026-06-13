---
hash: "ed8ba5bb"
id: "bdd0f6ee"
read_when: "deciding how the assurance-strategist eval harness isolates with-skill vs without-skill arms, or wanting the evidence behind the headless clean-room recipe (what was run, observed, and concluded)"
summary: "Tech spike (task 001) verifying clean-room isolation for headless `claude -p` eval runs: auth via copied credentials, config-dir relocation, skill discovery, the two required isolation conditions, and the built-in command floor. Verdict GO (conditional). The reusable recipe distilled from this lives in headless-claude-cli-evals.md."
title: "Spike: Clean-room isolation for assurance-strategist evals"
---

# Tech Spike Report: Clean-room isolation for assurance-strategist evals

**Date:** 2026-06-12
**Scope:** Can headless `claude -p` eval runs authenticate from the shared `~/.claude` while seeing NONE of this repo's content (project CLAUDE.md, 30+ installed skills, memory, hooks, MCP) — except optionally one skill-under-test?
**Verdict:** **GO (conditional).** The clean room works, but on two non-obvious conditions: (a) the workspace must live **outside the repo tree**, and (b) you must **not** pass `--setting-sources ''`. An irreducible floor of ~14 Claude Code built-in commands remains in both arms (harmless to the differential).

## Context

Task 001 needs an eval harness (`src/assurance/evals/eval.py`) that runs a coding prompt through `claude -p` twice — with and without the `assurance-strategist` skill — and compares. For the baseline ("without skill") arm to be meaningful, the agent must not inherit this repo's own skills/CLAUDE.md/hooks. Proposed approach (Charlie): relocate the config home to a tmp dir seeded with only the auth credentials copied from the real `~/.claude`.

## Assumptions Tested

| # | Assumption | Result | Confidence |
|---|-----------|--------|------------|
| 1 | Copying only `.credentials.json` into a fresh `CLAUDE_CONFIG_DIR` authenticates `claude -p` | **VALIDATED** | High |
| 2 | Baseline arm sees zero repo skills + no project/user CLAUDE.md | **VALIDATED (conditional)** | High |
| 3 | A skill at `$CLAUDE_CONFIG_DIR/skills/<name>/SKILL.md` loads as exactly one extra skill | **VALIDATED** | High |
| 4 | No hooks fire / no MCP servers attach in the clean room | **VALIDATED** | High |
| 5 (emergent) | A truly *zero-skill* baseline is achievable | **INVALIDATED** | High |

## Detailed Findings

### Assumption 1 — Auth via copied credentials — VALIDATED

Auth in this environment is a file (`~/.claude/.credentials.json`, mode 600); there is **no** `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` in the env. A config dir containing *only* that copied file authenticated every `claude -p` run (all exited 0 with real model output). The credentials snapshot is sufficient; no other config is needed for auth.

**Implication:** `eval.py` seeds each run's config dir with `cp ~/.claude/.credentials.json $CFG/`. If a token refresh occurs mid-run it writes back to the *clean* dir, preserving isolation. `eval.py` should fail fast if the source credentials file is absent.

### Assumption 2 — Baseline isolation — VALIDATED, on two conditions

Final clean baseline (workspace outside repo, config = creds only, default setting-sources):
```
SKILLS_START
deep-research / update-config / keybindings-help / verify / code-review / simplify /
fewer-permission-prompts / loop / schedule / claude-api / run / init / review / security-review
SKILLS_END
CLAUDE_MD: none
```
No project skills (`v1-new-task`, `v1-execute-task`, `planning-doc`, …) and no CLAUDE.md.

**Two conditions discovered the hard way:**

1. **Workspace MUST be outside the repo tree.** First attempts ran in `.tmp/` (under `/home/vscode/src/skills/`). Claude Code walks *up* from cwd and re-discovered the repo's project skills **and** CLAUDE.md regardless of `CLAUDE_CONFIG_DIR`. Moving the workspace to `/tmp/...` eliminated this. **`.tmp/` inside the repo is NOT isolated.**
2. **Do NOT pass `--setting-sources ''`.** It does isolate (zero skills, CLAUDE_MD none) — but it *also* suppresses discovery of the skill-under-test, breaking the with-skill arm. Omit the flag; isolation then comes from the clean config dir + out-of-repo cwd instead.

### Assumption 3 — Skill discovery path — VALIDATED

A personal skill at `$CLAUDE_CONFIG_DIR/skills/zzz-spike-marker/SKILL.md` loaded as exactly one extra entry; baseline (14) vs with-skill (15, the extra being `zzz-spike-marker`). `zzz-spike-marker` is an invented name the agent could only know by discovery — confirms the report is real, not hallucinated.

**Implication:** with-skill arm = drop the compiled `assurance-strategist` skill at `$CFG/skills/assurance-strategist/SKILL.md` (+ its `references/`). Baseline arm = same config dir minus that directory. The two arms differ by exactly one skill.

### Assumption 4 — Hooks / MCP — VALIDATED

The real `~/.claude/settings.json` carries a `PreToolUse` Bash hook (`dcg` — it blocked an `rm -rf` in *this* parent session) and an `mcp-agent-mail` MCP server. In the clean room the agent ran `echo SPIKE_BASH_OK` **without** dcg interference, and no MCP tools were present (`--strict-mcp-config` + no `mcpServers` in the clean config). The clean config dir + `--strict-mcp-config` neutralizes both.

### Assumption 5 (emergent) — Zero-skill baseline — INVALIDATED

~14 commands ship with the `claude` binary itself (`init`, `review`, `security-review`, `verify`, `run`, `code-review`, `simplify`, `deep-research`, `loop`, `schedule`, `update-config`, `keybindings-help`, `claude-api`, `fewer-permission-prompts`). `CLAUDE_CONFIG_DIR` cannot remove them — they are not config-dir content. Removing them would require disabling the Skill/SlashCommand tooling wholesale, which would also remove the skill-under-test.

**Implication:** accept this floor. It is **identical in both arms**, so it does not confound the with-vs-without differential. A few (`verify`, `code-review`, `run`, `simplify`) are assurance-adjacent, but they are slash commands the agent won't auto-invoke for a "build a calculator CLI" prompt. Note it in the eval report for honesty; don't fight it.

## Surprises & Secondary Findings

- The biggest risk was **not** auth (worked first try) — it was the **cwd walk-up** leaking project context. The intuitive choice (`.tmp/` per the tech-spike convention) is exactly the wrong place for the eval workspace.
- `--setting-sources ''` is a trap: it looks like the strongest isolation lever but silently disables the skill-under-test too.
- Default model for `claude -p` here is a mix (Haiku for trivial turns, Opus for the main turn); `eval.py` should pin `--model` for reproducible scorecards.

## Risks Identified

- **Credential expiry / refresh** mid-run — low risk; copy is per-run and writes back to the clean dir.
- **Built-in command floor** — accepted; constant across arms.
- **Fixture-provided context is intentionally live** — default setting-sources means if a fixture ships its own `.claude/` or CLAUDE.md, it WILL load. That's desirable (fixture is the target repo), but case authors must know a stray CLAUDE.md in a fixture is in-scope.

## Recommendations

**Proceed.** Final recipe for `eval.py`, per run:

1. `BASE=$(mktemp -d)` — **outside** the repo tree (use `mktemp`/`$TMPDIR`, never `.tmp/`).
2. `CFG=$BASE/config`; `cp ~/.claude/.credentials.json $CFG/`. Fail fast if missing.
3. with-skill arm only: write compiled skill to `$CFG/skills/assurance-strategist/` (SKILL.md + references/).
4. `WS=$BASE/ws`; copy the fixture into it.
5. Invoke with `cwd=WS`:
   ```
   CLAUDE_CONFIG_DIR=$CFG claude -p "<prompt>" \
     --output-format json --strict-mcp-config \
     --permission-mode bypassPermissions --model <pinned> < /dev/null
   ```
   (Do **not** pass `--setting-sources ''`.)
6. Parse `.result` from the JSON envelope; keep the full JSON as the run's evidence.
7. Baseline arm = identical, minus step 3.

This satisfies AC-4/AC-5: the two arms are byte-identical except for one skill directory, so the output diff is attributable to `assurance-strategist`.

## Appendix: Reproduction

- Spike scratch (gitignored): `.tmp/spike-iso-a/`, `.tmp/spike-iso-b/` (inside-repo runs showing leakage).
- Clean two-arm run: `/tmp/eval-spike-<pid>/{baseline,withskill}/{config,ws}/out.json` (ephemeral).
- Probe prompt: agent runs `echo SPIKE_BASH_OK`, then emits a `SKILLS_START/END` + `CLAUDE_MD:` report as its final message; compare arms via `jq -r '.result'`.
- Tools used: `claude` 2.1.175, `jq`, `python3` — all preinstalled.
