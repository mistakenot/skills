# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-20250514
- **Skill version**: 0c9298f
- **Timestamp**: 2026-06-16 17:54:29 UTC

- **baseline cost**: $0.0000
- **withskill cost**: $0.0000

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | True |
| Verify entry point | False | True |
| Tests directory | False | True |
| Test command (T2) | absent | make test (ran, exit 0) |

## Gotcha Probes

Mechanical anti-pattern checks (a defect when triggered). See `graders/gotchas.md`.

| Gotcha | Baseline | With-skill |
|--------|----------|------------|
| G1 Fake PBT (claims properties, no PBT library) | no | no |
| G2 Over-prescribed property layer | no | no |
| G3 Randomness without determinism | n/a | n/a |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 0 | 3 |
| Verify command | 0 | 3 |
| Test quality | 0 | 2 |
| Evidence of verification | 0 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
