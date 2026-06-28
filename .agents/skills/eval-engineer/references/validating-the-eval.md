# Validating the eval before you trust it

An A/B between two skill versions is only meaningful if the harness can tell a real
difference from run-to-run randomness. Agent runs are non-deterministic — the same skill on
the same input varies in tokens, time, and output depth. So before you compare arms, you
characterise the instrument. Three checks, in order.

## 1. Noise floor — the most important number you'll measure

Run the **same arm** on the **same fixture** at least **3 times** (more if you can afford it).
Look at the spread:

- `max / min` on tokens and wall-clock — your multiplicative noise.
- variation in the quality signal (AC count, structure, lint).

That spread is your **detection threshold**. A difference between arms smaller than it is not
a finding. Worked example from `planning-eval` (three identical v2 runs of one fixture):

| run | wall | sessions (fan-out) | tokens | AC cards |
|-----|------|--------------------|--------|----------|
| 1 | 787s | 3 | 17.3M | 7 |
| 2 | 1390s | 7 | 26.3M | 12 |
| 3 | 865s | 4 | 17.0M | 9 |

Spread: **1.55× tokens, 1.77× wall** on *identical* inputs. Conclusion: any single-run
comparison there is worthless; a real win must beat ~1.8× or be shown across a trial
distribution. Note *what drives* the variance — here it was variable subagent fan-out (3→7),
which happened to be the very thing the new skill aimed to stabilise. The noise was a
symptom of the disease, which is a good sign the metric points at the right thing.

## 2. Quality floor — is the output reliably valid?

Across those same runs, confirm the output is consistently **complete and valid** by some
cheap mechanical check (it lints clean; it has the expected tabs/sections/fields; the
transform round-trips). If quality itself swings wildly run-to-run, you can't attribute a
quality change to a skill — you're seeing the floor move. A stable floor with varying *depth*
(more/fewer details) is normal and fine; varying *validity* is a problem to fix before A/B.

## 3. Generality — does it work on a second task?

Author and run a **second fixture**. If the harness only works on the one task you tuned it
against, you're measuring that task, not the skill. A second fixture also surfaces
fixture-authoring assumptions that didn't generalise.

## What validation buys you

Once you know the noise floor you know:

- **How many trials per arm** you need (enough that the median is stable relative to the
  spread — usually ≥3, more if noise is high).
- **How big a difference counts** — anything under the noise floor needs more trials or is a
  non-result.
- **Which cheap proxy to watch** — find the one metric that moved most with both cost and the
  variable under study (fan-out / `session_count` in planning-eval), so future runs are fast
  to read.

## Reading the A/B

- Compare **medians of ≥3 trials per arm**, not single runs. Report the distribution (min /
  median / max), not just a point estimate.
- Report **both axes** — velocity (tokens, wall, tool-time, fan-out) and quality (the
  mechanical floor + a judgement pass). The headline is **quality-per-token**: cheaper at
  equal-or-better quality. A cheaper arm that does less is not a win; flag it.
- Velocity and quality are usually **coupled** (spend more → produce more), so hold one axis
  or normalise. "v3 matched v2's completeness at 0.5× the tokens" is a clean claim; "v3 was
  faster" is not.

## Cost discipline

Validation isn't free: noise floor (≥3) + generality (a 2nd fixture) + the A/B (≥3 × 2 arms)
is a dozen-plus real runs. Price it up front, start with the smallest viable fixtures, and
run with the metrics-ingest step deferred (`--no-metrics` style) when iterating on plumbing,
collecting metrics once at the end.
