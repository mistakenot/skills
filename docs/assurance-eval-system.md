---
hash: "e5d84480"
id: "7ceb6cc2"
read_when: "running evals, adding new eval cases, or understanding how the with-skill vs without-skill comparison works"
summary: "Two-arm differential eval harness for the assurance-strategist skill: architecture, how to run (stub vs live), mechanical checks (T1/T2), grader dimensions, how to add new cases and dimensions."
title: "Assurance Eval System"
---

# Assurance Eval System

Two-arm differential eval harness for the `assurance-strategist` skill. Compares agent output with and without the skill installed against the same build prompt, producing a scored comparison report.

## Architecture

```
run.sh (orchestrator)
  ├── baseline arm:   claude -p <prompt>  (no skill)
  ├── withskill arm:  claude -p <prompt>  (skill installed)
  ├── checks.sh:      mechanical T1/T2 scorecard per arm
  ├── grader:          claude -p <rubric + both arms>  → scored JSON
  └── grade_report.py: assemble report.md from all artifacts
```

Each arm runs in a clean-room temp directory outside the repo with a relocated `CLAUDE_CONFIG_DIR`. The two arms differ by exactly one skill directory. See [headless-claude-cli-evals.md](headless-claude-cli-evals.md) for the isolation recipe.

## Running evals

### Stub mode (no API calls, deterministic)

```bash
make eval-assurance AGENT_RUNNER=stub
```

Uses canned JSON outputs. Verifies the full pipeline (checks, grading, report assembly) without credentials or cost.

### Live mode

```bash
make eval-assurance
```

Requires `~/.claude/.credentials.json`. Makes ~3 API calls (baseline arm, withskill arm, grader).

### Options

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `claude-sonnet-4-20250514` | Model for all arms |
| `AGENT_RUNNER` | `live` | `stub` for offline mode |
| `CASE` | `calculator-cli` | Case directory name under `cases/` |

## Output

Each run creates `src/assurance/evals/results/run-<timestamp>/`:

| File | Git-tracked | Purpose |
|------|-------------|---------|
| `report.md` | Yes | Scores + human verdict (durable evidence) |
| `*/out.json` | No | Raw `claude -p` transcripts |
| `*/scorecard.json` | No | Mechanical check results |
| `grader.json` | No | Grader dimension scores |

## Mechanical checks (T1/T2)

`checks.sh` probes the agent's workspace and emits JSON. Always exits 0.

**T1 — file probes** (boolean):
- `t1_testing_doc`: testing documentation exists (TESTING.md, tests/README.md, etc.)
- `t1_verify_entry`: runnable test entry point (Makefile test target, package.json test script, etc.)
- `t1_tests_dir`: test files/directories exist

**T2 — test execution**:
- Probes in order: `make verify` → `make test` → `npm test` → `pytest`
- If found: runs it, records command + exit code
- If not found: `{"t2_command":"none","t2_status":"absent","t2_exit":null}`

A non-zero exit or absent test command is a valid recorded outcome, not an eval failure.

## Grader

A third `claude -p` call (no skill) scores both arms on four dimensions (0-3 scale):

| Dimension | What it measures |
|-----------|-----------------|
| `tests_present` | Did the agent create test files? |
| `verify_command` | Is there a way to run the tests? |
| `test_quality` | Are the tests meaningful (not stubs)? |
| `evidence` | Did the agent verify its own work? |

The rubric lives at `src/assurance/evals/graders/strategy-rubric.md`. `grade_report.py` parses the grader's JSON defensively (strips code fences, extracts first balanced `{...}` block, degrades to "parse failed" row on failure).

## Adding a new eval case

1. Create `src/assurance/evals/cases/<name>/prompt.md` with the build prompt
2. Create `src/assurance/evals/cases/<name>/checks.sh` (must be executable):
   - Takes one argument: workspace directory path
   - Emits a single JSON object with T1/T2 fields to stdout
   - Must always exit 0 with valid JSON
3. Run: `make eval-assurance CASE=<name>`

The grader rubric is shared across cases. If a case needs a custom rubric, create `graders/<name>-rubric.md` and update `run.sh` to select it.

## Adding a new grader dimension

1. Add the dimension to `src/assurance/evals/graders/strategy-rubric.md` (key name + scoring criteria)
2. Add the key to the `dimensions` list in `grade_report.py:render_report()` and `dim_labels` dict
3. The stub grader in `run.sh:run_grader_stub()` should include the new key in its canned JSON

## File layout

```
src/assurance/evals/
  run.sh                           # orchestrator (clean-room + process control)
  grade_report.py                  # report assembly (stdlib-only python)
  cases/
    calculator-cli/
      prompt.md                    # build prompt
      checks.sh                   # mechanical T1/T2 checks
  graders/
    strategy-rubric.md            # grader prompt (pins dimensions + JSON shape)
  results/
    .gitkeep
    run-<timestamp>/              # per-run output (artifacts gitignored, report.md tracked)
```
