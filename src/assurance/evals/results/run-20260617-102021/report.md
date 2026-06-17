# Eval Report

- **Case**: uk-tax-calculator
- **Model**: claude-sonnet-4-6
- **Skill version**: a9f78e2
- **Timestamp**: 2026-06-17 10:28:55 UTC

- **baseline cost**: $0.3621
- **withskill cost**: $0.8049
- **Skill invoked**: yes

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | False |
| Verify entry point | False | False |
| Tests directory | True | True |
| Test command (T2) | absent | pytest (ran, exit 0) |

## Gotcha Probes

Mechanical anti-pattern checks (a defect when triggered). See `graders/gotchas.md`.

| Gotcha | Baseline | With-skill |
|--------|----------|------------|
| G1 Fake PBT (claims properties, no PBT library) | ⚠️ yes | no |
| G2 Over-prescribed property layer | no | no |
| G3 Randomness without determinism | n/a | no |
| G4 Band boundaries absent from tests (uk-tax-calculator only) | no | no |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 3 | 3 |
| Verify command | 2 | 2 |
| Test quality | 3 | 3 |
| Evidence of verification | 1 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
