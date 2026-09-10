---
name: consult-the-council
description: "Consults a council of independent coding-agent models (claude, codex, gemini, opencode, grok) for diverse, unled opinions on a question, blind and read-only, then maps agreement and disagreement. Use when 'consult the council', 'second opinions', 'what would other models say', 'pre-mortem this', 'red-team this plan', or before a hard-to-reverse decision. Not for reviewing task docs (use request-council-review)."
---

# Consult the council

Put one question to several independent models and get back the spread of
their answers, not a vote. The members never write files and never see each
other's answers in the first round; the parent frames the question so as not
to lead them, collects the answers verbatim, synthesises them blind, and only
then learns which model said what.

This is an explore step. A single model, asked twice, mostly agrees with
itself; models from different families make different mistakes, so the
disagreements between them are where the unconsidered options and the hidden
assumptions live. The design follows the conditions under which a crowd beats
its members (diversity, independence, aggregation) and borrows its strategies
from Delphi, nominal-group technique, pre-mortems and dialectical inquiry.

## The SDK: three axes

Every consultation is an assembly of one choice from each axis. Pick them in
this order.

| Axis | Choices | Reference |
| ---- | ------- | --------- |
| **Strategy** | `blind-round` (default), `pre-mortem`, `red-team`, `dialectic`, `delphi` | one file per strategy under `references/strategies/` |
| **Members** | any of `claude`, `codex`, `gemini`, `opencode`, `grok`; default all available, preference in that order; plus access `repo` (read-only, default) or `none` | one file per member under `references/members/` |
| **Prompt** | `open-question`, `options-symmetric`, `critique-proposal`, `pre-mortem`, `estimate`, `delphi-round-2` | `references/prompts/templates.md` |

Choosing a strategy:

- No proposal yet, want the space mapped → `blind-round`.
- A plan exists, want its failure modes → `pre-mortem`.
- A proposal exists, want it attacked → `red-team` (after a blind round if
  you can afford both).
- A decision is expensive to reverse, want the best case each way →
  `dialectic` (second round only).
- Need the council to converge on a position → `delphi`.

Each strategy file names the prompt templates it pairs with and its
aggregation rule. Read the chosen strategy file before running; read the
member files only when a member misbehaves or you need to change its access.

## Invariants (every assembly)

1. **Neutral framing.** Read `references/prompts/neutral-framing.md` before
   writing the prompt file, every time. Fewer instructions is better: state
   the situation, ask one open question, withhold your own view. This is the
   step that decides whether the council is worth its cost.
2. **Independence in round one.** No member sees another's answer, or is told
   that others are answering. One prompt file, sent verbatim to all.
3. **Read-only members.** Every invocation the script makes is a plan mode or
   read-only sandbox; members produce text, nothing else. Do not add write
   flags to get "more capable" answers.
4. **Verbatim before synthesis.** The raw answers are kept and reported. A
   synthesis the parent cannot check against them is a summary, not evidence.
5. **Blind synthesis, key after.** Cluster the answers as A, B, C; read
   `key.json` only when the synthesis is written.

## Workflow

1. **Frame.** Write the question to a file using the chosen template. Apply
   the self-check in `neutral-framing.md`: could a member say "do something
   else entirely" without contradicting anything you wrote?

2. **Run.** The script first probes every requested member with a one-line
   prompt through its real read-only argv (preflight), drops the ones that
   are missing, not logged in, hung or returned nothing, and proceeds with
   the rest if they make quorum. Then it fans the question out in parallel,
   closes stdin, strips each CLI's noise, and writes one answer file per
   member under blind labels:

   ```bash
   SKILL_DIR="$CLAUDE_SKILL_DIR"   # or wherever this skill is installed
   uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file q.md --out "$OUT"
   ```

   Quorum is 3 by default, or all requested members when fewer are asked
   for. Below quorum the script stops with exit code 3 and lists each broken
   member with its fix (`grok login`, `export GEMINI_API_KEY=...`, install
   it). Relay that to the user and stop; do not lower `--quorum` on your own
   to make a council of one. A council that lost a member or two still runs
   and says so (`proceeding without gemini, grok`); note the missing
   families in the report, since fewer families means less diversity.

   Options: `--members claude,codex` (subset, always run in preference
   order), `--access none` (empty directory instead of read-only repo),
   `--cwd DIR` (repo root, default current directory), `--timeout SECS`
   (default 600), `--quorum N`, `--skip-preflight` (you just ran
   `preflight` yourself), `--attributed` (skip blinding), `--runner stub`
   (canned answers, for dry runs). `preflight` on its own reports who is
   usable without asking anything; `argv --member M` prints a member's exact
   command.

   The summary reports each member as `ok`, `auth`, `timeout`, `error` or
   `missing`. A member that passes preflight but fails the real question does
   not block the others. Exit code 1 means at least one did not answer.

3. **Synthesise** per `references/synthesis.md`: read all answers, cluster
   by recommendation, name the disagreements and the assumption each turns
   on, keep minority views, collect the open questions members raised. Then
   `council.py reveal --out "$OUT"` and append the key.

4. **Report** using the structure in `synthesis.md`: question, verbatim
   answers (or the output directory), clusters, disagreements, minority
   views, open questions, key. For an explore strategy do not conclude
   "the council recommends"; say what converged and what the split turns on.

## Reference map

| File | Read when |
| ---- | --------- |
| [references/prompts/neutral-framing.md](references/prompts/neutral-framing.md) | Always, before writing the prompt. Required. |
| [references/prompts/templates.md](references/prompts/templates.md) | Choosing or filling a prompt template. Required. |
| [references/strategies/blind-round.md](references/strategies/blind-round.md) | Running `blind-round`. Required for it. |
| [references/strategies/pre-mortem.md](references/strategies/pre-mortem.md) | Running `pre-mortem`. Required for it. |
| [references/strategies/red-team.md](references/strategies/red-team.md) | Running `red-team`. Required for it. |
| [references/strategies/dialectic.md](references/strategies/dialectic.md) | Running `dialectic`. Required for it. |
| [references/strategies/delphi.md](references/strategies/delphi.md) | Running `delphi`. Required for it. |
| [references/synthesis.md](references/synthesis.md) | Before synthesising. Required. |
| [references/members/claude.md](references/members/claude.md), [references/members/codex.md](references/members/codex.md), [references/members/gemini.md](references/members/gemini.md), [references/members/opencode.md](references/members/opencode.md), [references/members/grok.md](references/members/grok.md) | A member fails, needs different access, or you need its exact flags. Optional. |

## Guard rails

- The flags the script passes are pinned in this repo's agent CLI contract
  and checked against the installed CLIs by `make test`; if a member errors
  on a flag, run that first.
- `opencode` is a harness: its model comes from its own config, and it only
  adds diversity if that model is from a family the other members lack. The
  banner line in its `.log` names the model.
- The parent is usually Claude Code, so the `claude` member is the parent's
  own family. Its answer counts, but if it alone agrees with your prior,
  that is one family agreeing with itself.
- Not for reviewing task planning docs: `request-council-review` does that
  with comments left in the docs. This skill never writes anything.
