# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-20250514
- **Skill version**: 0c9298f
- **Timestamp**: 2026-06-15 15:23:36 UTC

- **baseline cost**: $0.5324
- **withskill cost**: $1.3185
- **Skill invoked**: yes

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | False |
| Verify entry point | False | True |
| Tests directory | True | True |
| Test command (T2) | absent | make verify (ran, exit 2) |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 3 | 3 |
| Verify command | 0 | 3 |
| Test quality | 2 | 3 |
| Evidence of verification | 1 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
