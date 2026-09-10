---
hash: "01f40931"
id: "920f10ef"
read_when: "changing the new-epic skill (seams, assumption register, DAG shaping) and needing the pre-change baseline, the noise floor between identical runs, or the known defects the baseline already shows"
summary: "Baseline run of the unmodified new-epic skill on the auto-stack-multi-host-epic scenario (two identical trials, 2026-09-10): what the current skill produces, how much two trials of the same skill differ, and the defects visible before any seam work — including zero recommendedAnswer attributes despite the skill instructing them and the final message claiming them."
title: "new-epic — eval baseline on the auto-stack epic 003 scenario"
---

# new-epic — eval baseline on the auto-stack epic 003 scenario

Run `20260910-143416-4987dd6` (`src/evals/runs/`, gitignored — findings
recorded here). One arm, `WORKTREE` at commit `2353b6c`, two trials, model
`claude-sonnet-4-6`, `--invoke instructed`, `--with rich-doc`. Scenario:
[`auto-stack-multi-host-epic`](../../src/evals/scenarios/auto-stack-multi-host-epic/README.md),
which pins auto-stack at the parent of the commit that added the real epic 003
and hands the agent the initiative brief with no mention of seams or tasks.

Purpose: the noise floor and the pre-change baseline for the seam /
assumption-register work on `new-epic`. Any A/B of that change has to beat the
spread below, not just differ from one trial.

## Cost and shape

| | trial 1 | trial 2 |
|---|---|---|
| cost | $1.92 | $1.43 |
| wall clock | 9.0 min | 6.6 min |
| turns | 33 | 26 |
| output | `epic-003-multi-host-watch-backend.html`, 35 KB | `epic-003-watch-backend-ui-proxy.html`, 34 KB |
| guard rails | 6 | 5 |
| tasks | 6 | 6 |
| open questions | 6 | 4 |
| decisions | 4 | 3 |

Both trials invoked the skill, both wrote a four-tab epic in the repo's
convention, both linted clean apart from open questions.

## Noise floor: what two trials of the same skill disagree on

- **DAG shape.** Trial 1 is shallow and wide: T1 (skeleton) fans out to four
  tasks, one merge at T5. Trial 2 is a chain: T1 → {T2, T3} → T4 → T5, with T6
  hanging off T2. Same skill, same prompt, opposite shapes on the axis the
  seam work cares about.
- **Seam concreteness.** Trial 2's Architecture tab has an RPC method table,
  an HTTP route table, a `backends.json` schema and proxy routing rules —
  incidentally close to what a seam contract should be. Trial 1 lists what
  moves between containers with no shapes at all. Neither uses the word
  "seam" or names contracts as such, though `epic-tabs.md` asks for exactly
  that.
- **Task boundaries.** Both have six tasks and a walking skeleton first, but
  the six are cut differently (trial 1 has a security task; trial 2 has a
  task-dispatch task).

Conclusion: seam concreteness already varies from "none" to "nearly there"
between identical runs. A seam change to the skill must be judged on ≥2
trials per arm, and the question is whether it makes the *floor* concrete,
not whether one run looks good.

## Defects visible before any change

1. **No `recommendedAnswer` attributes.** Zero in both trials, despite
   `new-epic` step 8 instructing them. The leans exist as prose in each
   question body. Trial 1's final message states "six `pd-question` elements
   … with `recommendedAnswer` on each" — a false self-report. `new-task-quick`
   guards this with a grep before stopping; `new-epic` has no such
   self-check. Fix independently of the seam work.
2. **Identity collision not caught.** Trial 2 routes browser RPCs "to the
   correct backend based on the `project` field". The real epic's review
   caught that project id alone collides across hosts and added GR-F8
   `(hostId, projectId)`. Trial 1 shows a host badge but never states the
   identity rule either. This is the kind of load-bearing assumption an
   assumption register should surface.
3. **Transport seam absent.** The real epic's first named seam is the
   `Listener`/`Dialer` transport abstraction (unix socket vs TCP, and the
   decision against WebSocket between daemons). Both trials chose WebSocket
   everywhere without recording it as a decision with alternatives.
4. **No assumption register, no invalidation protocol, no per-edge
   contracts.** Expected — this is the change under evaluation.

## What the ground truth has that neither trial has

Real epic 003: 16 guard rails vs 5–6; 10 tasks vs 6; five named seams with
owning packages; a scenario-to-transport table; the data/control plane split
for events; three review threads that changed the doc before execution. Task
042's feedback later recorded a `doc.raw` shape drift (base64 vs raw bytes)
on a seam the epic had named but not specified — the failure the seam work
is meant to prevent.

## Harness notes from this run

- `REPORT.md` reported *no output file* for both trials: the deliverable lands
  in `ws/auto-stack/docs/epics/`, and the report only scanned the `ws/`
  root. Fixed after this run: outputs are now files new or changed relative
  to the scenario seed.
- `--with rich-doc` behaved: the companion was installed on the arm, absent
  on the (unused) baseline, and named in the report.
