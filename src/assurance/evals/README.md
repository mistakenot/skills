# Assurance Eval Harness

Two-arm eval harness for the `assurance-strategist` skill. Runs a baseline agent (no skill) and a with-skill agent against the same build prompt, then compares their outputs mechanically and via a grader.

## Quick start

### Stub mode (deterministic, no API calls)

```bash
make eval-assurance AGENT_RUNNER=stub
```

Uses canned outputs instead of calling the Claude API. Useful for verifying the pipeline (checks, grading, report assembly) without credentials or cost.

### Live mode

```bash
make eval-assurance
```

Requires `~/.claude/.credentials.json` (Claude Code auth). Runs real `claude -p` calls for both arms and the grader. Expect ~3 API calls per run.

### Options

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `claude-sonnet-4-20250514` | Model to pin for all arms |
| `AGENT_RUNNER` | `live` | `stub` for offline/deterministic mode |
| `CASE` | `calculator-cli` | Case directory under `cases/` |

## Output

Each run produces `results/run-<timestamp>/`:

| File | Tracked | Description |
|------|---------|-------------|
| `report.md` | Yes | Mechanical + grader scores, human verdict section |
| `baseline/out.json` | No | Raw claude -p output (baseline arm) |
| `withskill/out.json` | No | Raw claude -p output (with-skill arm) |
| `baseline/scorecard.json` | No | Mechanical T1/T2 checks (baseline) |
| `withskill/scorecard.json` | No | Mechanical T1/T2 checks (with-skill) |
| `grader.json` | No | Grader dimension scores |

`report.md` is git-tracked (the durable evidence carrier); all other run artifacts are gitignored.

## Clean-room isolation

Both arms run in isolated temp directories outside the repo tree, with a relocated `CLAUDE_CONFIG_DIR`. The two arms differ by exactly one skill directory. See [docs/headless-claude-cli-evals.md](../../../docs/headless-claude-cli-evals.md) for the full isolation recipe and gotchas.

## Adding cases

1. Create `cases/<name>/prompt.md` with the build prompt
2. Create `cases/<name>/checks.sh` (executable) that takes a workspace dir and emits T1/T2 JSON
3. Run: `make eval-assurance CASE=<name>`
