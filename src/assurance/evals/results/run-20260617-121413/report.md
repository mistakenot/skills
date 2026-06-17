# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-6
- **Skill version**: bf7b0a8
- **Timestamp**: 2026-06-17 12:14:14 UTC

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
| G4 Band boundaries absent from tests | ? | ? |
| G5 No server/store function tests | ? | ? |
| G6 No component-level tests | ? | ? |
| G7 E2E without unit/component layer | ? | ? |
| G8 No test framework configured | ? | ? |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 0 | 3 |
| Verify command | 0 | 3 |
| Test quality | 0 | 2 |
| Evidence of verification | 0 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
