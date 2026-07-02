# Instrument validation — strategy-only blind eval (2026-07-02)

Recorded noise floor + blinding-leakage measurement for the strategy-only
blind-differential mode, per **AC-5** (noise floor) and **AC-6** (leakage
accuracy). Produced by `validate-instrument.sh` (3 full blind A/B runs, each
both arms + a blind judge, with a distinct anonymisation seed per run so the
A/B order varies and leakage isn't a fixed-order artifact).

- **Case**: `strategy/marketing-landing-page` (over-engineering trap)
- **Model**: `claude-sonnet-4-6`
- **Runs**: 3

## Per-run

| Run | Seed | A/B order | Winner | Skill-guess | Total cost |
|-----|------|-----------|--------|-------------|------------|
| 1 | 42 | A=withskill B=baseline | baseline | correct | $0.426445 |
| 2 | 43 | A=baseline B=withskill | baseline | correct | $0.591196 |
| 3 | 44 | A=baseline B=withskill | baseline | correct | $0.470506 |

## Noise floor

- **Winner stability**: **STABLE** — `baseline` won 3/3. The order flipped
  between runs (seed varied), so the verdict is not an artifact of A/B position.
- **Cost spread**: min $0.426445 · max $0.591196 · **range $0.164751**.

**Detection threshold**: a verdict that flips run-to-run, or an A/B cost
difference smaller than the observed **$0.165** spread, is **noise, not signal**.
Read any future skill-version A/B delta against this floor.

## Blinding leakage (AC-6)

- **Leakage accuracy: 3/3** — the blind judge correctly guessed which strategy
  came from the skill in every run.

**Interpretation (accepted risk, ADR-0001 / D-4):** high leakage means
house-style tells (structure, verbosity, section conventions) are identifying
the skill arm, so a *win* by the skill arm should be **discounted**. It is a
recorded finding and the **trigger to escalate anonymisation** (format
normalisation / stronger substance-only judge instruction) as a follow-up — it
is **not a blocker** for this task. Note that in this validation the skill arm
*lost* 3/3 anyway; leakage matters most when interpreting skill-arm wins.

## Reproduce

```bash
N=3 CASE=strategy/marketing-landing-page AGENT_RUNNER=live \
  bash src/assurance/evals/validate-instrument.sh
```

Run dirs for this record:
`results/run-20260702-233236`, `results/run-20260702-233648`,
`results/run-20260702-234225`.
