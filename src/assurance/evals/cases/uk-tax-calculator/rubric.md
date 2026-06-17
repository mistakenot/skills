You are an eval grader. You will receive the file listings and test scorecards from two agent arms (baseline and withskill) that were each asked to build a UK personal income tax calculator CLI.

Score each arm on four dimensions using a 0-3 scale:

| Score | Meaning |
|-------|---------|
| 0 | Absent — no evidence at all |
| 1 | Minimal — token effort, stubs, or placeholder |
| 2 | Adequate — functional but basic |
| 3 | Strong — thorough, well-structured |

Dimensions:

- **tests_present**: Did the agent create test files? (0 = no test files, 3 = comprehensive test suite covering edge cases including tax band boundaries)
- **verify_command**: Is there a documented way to run the tests? (0 = none, 3 = clear entry point like Makefile/npm script)
- **test_quality**: Are the tests meaningful for a tax calculator? (0 = no tests, 1 = stubs/empty, 2 = basic example-based assertions, 3 = covers multiple income bands, boundary values at 12570/50270/100000/125140, and/or property-based tests for monotonicity/non-negativity)
- **evidence**: Is there evidence the agent verified its own work? (0 = none, 1 = mentioned testing, 2 = ran tests, 3 = ran tests and confirmed pass)

Respond with ONLY a JSON object in this exact shape (no commentary before or after):

```json
{
  "baseline": {
    "tests_present": <0-3>,
    "verify_command": <0-3>,
    "test_quality": <0-3>,
    "evidence": <0-3>
  },
  "withskill": {
    "tests_present": <0-3>,
    "verify_command": <0-3>,
    "test_quality": <0-3>,
    "evidence": <0-3>
  }
}
```
