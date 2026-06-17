# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-6
- **Skill version**: 0c9298f
- **Timestamp**: 2026-06-17 09:44:57 UTC

- **baseline cost**: $0.1705
- **withskill cost**: $0.4959
- **Skill invoked**: yes

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | True |
| Verify entry point | False | True |
| Tests directory | True | True |
| Test command (T2) | absent | make verify (ran, exit 2) |

## Gotcha Probes

Mechanical anti-pattern checks (a defect when triggered). See `graders/gotchas.md`.

| Gotcha | Baseline | With-skill |
|--------|----------|------------|
| G1 Fake PBT (claims properties, no PBT library) | no | no |
| G2 Over-prescribed property layer | no | no |
| G3 Randomness without determinism | n/a | no |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 3 | 3 |
| Verify command | 1 | 3 |
| Test quality | 3 | 3 |
| Evidence of verification | 1 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
