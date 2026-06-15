# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-20250514
- **Skill version**: dc97046
- **Timestamp**: 2026-06-15 12:28:05 UTC

- **baseline cost**: $0.3959
- **withskill cost**: $1.3309
- **Skill invoked**: yes

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | False |
| Verify entry point | False | True |
| Tests directory | True | True |
| Test command (T2) | absent | make verify (ran, exit 0) |

## Grader Scores

| Dimension | Baseline | With-skill |
|-----------|----------|------------|
| Tests present | 3 | 3 |
| Verify command | 0 | 3 |
| Test quality | 3 | 3 |
| Evidence of verification | 1 | 3 |

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
