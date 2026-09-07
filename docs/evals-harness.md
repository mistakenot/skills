---
hash: "e747dee2"
id: "5cee9ee2"
read_when: "deciding whether to A/B a skill change with the evals harness, or needing to know what an evals run cannot tell you before trusting its result"
summary: "Orientation for the `src/evals/` harness: what it does, when to reach for it instead of planning-eval or the assurance harness, and the six limitations that bound what a run can tell you. The module README is the reference."
title: "evals — contained A/B harness for skill versions"
---

# evals — contained A/B harness for skill versions

`src/evals/` runs one task against one or more **arms** — an arm being a specific
version of a skill, or no skill at all — each in an isolated clean room, and
leaves a run directory a human reads side by side. Judgement is the human: no
graders, no LLM judges, no rubrics. The one automated check is whether the skill
actually fired, because that failure is silent and self-deceiving — if the skill
never loaded, both arms are the same run.

**The reference is [`src/evals/README.md`](../src/evals/README.md).** It covers
arms, scenarios, the run directory, the invocation check, the isolation canaries,
and the findings behind the design. This page is orientation and the limitations
summary.

## When to reach for it

| Shape | Harness |
|---|---|
| One prompt fully determines the output (generate a doc, transform a file) | **`src/evals/`** — this tool |
| The skill hard-stops and waits for a human, or quality depends on the back-and-forth | `src/planning-eval/` (NTM-driven, multi-turn) |
| You want mechanical checks and an LLM judge over a with/without differential | `src/assurance/evals/` |
| "Does the right skill fire for the right query?" | trigger evals (skill-creator's description optimizer) |

The `eval-engineer` skill routes between these and covers validating an eval
before trusting it.

## Limitations

Each is stated in full, with the specific failure, in the README's
[Limitations](../src/evals/README.md#limitations) section. In short:

1. **Claude-only.** `stream.jsonl` parsing is specific to Claude Code's
   `stream-json`; another host makes every arm report NOT INVOKED. The Compound
   Engineering trailer protocol ([compound-engineering-evals.md](compound-engineering-evals.md))
   is the migration path.
2. **With/without under `--invoke instructed` carries a prompt confound** — you
   cannot tell an arm to invoke a skill it does not have, so the arms differ in
   prompt as well as in skill. Prefer `organic` where the skill routes reliably.
3. **N=1 by default.** One pair can mislead; `--n` does no statistics. `REPORT.md`
   always states the trial count.
4. **Component-library confound for `rich-doc`** — it fetches `llms.txt` from a
   CDN tag baked in at compile time, so two arms can differ by component version
   as well as by SKILL.md. Pin both arms to the same version.
5. **Not a sandbox.** `bypassPermissions` with real credentials in a temp dir.
   Fixtures must be disposable.
6. **Never in CI.** A live run bills real tokens. Only the stub lane and
   `pytest src/evals/tests/` are safe to automate.

## Related

- [headless-claude-cli-evals.md](headless-claude-cli-evals.md) — the clean-room isolation recipe the cell implements, the CLI flags, and the built-in skill floor (measure it, never hard-code it).
- [assurance-eval-system.md](assurance-eval-system.md) — the two-arm harness the cell was lifted from.
