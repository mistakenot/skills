# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-20250514
- **Skill version**: dc97046
- **Timestamp**: 2026-06-15 13:36:11 UTC

- **baseline cost**: $0.7442
- **withskill cost**: $0.8928
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
| Test quality | 3 | 3 |
| Evidence of verification | 1 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
