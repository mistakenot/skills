# Eval Report

- **Case**: tanstack-fullstack
- **Model**: claude-sonnet-4-6
- **Skill version**: 9466da8
- **Timestamp**: 2026-06-17 13:22:55 UTC

- **baseline cost**: $1.0542
- **withskill cost**: $1.2167
- **Skill invoked**: yes

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | True | True |
| Verify entry point | True | True |
| Tests directory | True | True |
| Test command (T2) | npm test (ran, exit 0) | make verify (ran, exit 0) |

## Gotcha Probes

Mechanical anti-pattern checks (a defect when triggered). See `graders/gotchas.md`.

| Gotcha | Baseline | With-skill |
|--------|----------|------------|
| G1 Fake PBT (claims properties, no PBT library) | ⚠️ yes | no |
| G2 Over-prescribed property layer | no | ⚠️ yes |
| G3 Randomness without determinism | n/a | no |
| G4 Band boundaries absent from tests | ? | ? |
| G5 No server/store function tests | no | no |
| G6 No component-level tests | no | ⚠️ yes |
| G7 E2E without unit/component layer | n/a | n/a |
| G8 No test framework configured | no | no |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 3 | 2 |
| Verify command | 3 | 3 |
| Test quality | 3 | 2 |
| Evidence of verification | 3 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
