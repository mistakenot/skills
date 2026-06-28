# Building fixtures from real tasks

A fixture replays a real task under controlled conditions. Real-task replay beats synthetic
prompts because it matches how the skill is actually used and because the *outcome* (the
docs/code that task produced) is available as ground truth.

A fixture pins down:

- **target repo** + an **immutable start SHA** — the repo state *before* the task was done.
- **prompt** — the operator's opening request, verbatim where possible.
- **human_turns** — the steering the operator gave as the work progressed (for interactive
  skills); sent in order.
- **limits** — turn / wall-clock / per-turn caps so a run always terminates.

## Finding a clean start SHA (avoid contamination)

The agent must start from a state where the answer isn't already present. If the finished
plan or implementation is in the checkout, the agent can copy it and the eval is meaningless.

- Find the commit that introduced the task's output, then use its **parent** as the start SHA:
  `git -C <repo> rev-parse <commit>^`.
- **Confirm it's clean**: `git -C <repo> ls-tree <sha> | grep <feature>` should be empty.
- **Beware squashed history.** Some repos commit the planning docs *together with* the
  implementation in one squashed commit — then the docs' git history gives the wrong
  boundary. Derive the boundary from the **session timestamp** (when planning actually
  happened) instead, and verify the parent is impl-free.
- **Pin an immutable SHA**, never `HEAD`/`main` — those drift and make runs unreproducible.

## Two authoring methods for prompt + human_turns

Pinpointing a task's real planning/work thread is the genuinely hard, manual part, and it's
*inconsistent* across tasks. Pick the method by what the task offers:

### Session-mined (higher fidelity)

Reconstruct the prompt and turns from the actual session transcript.

- Find the session: search the session corpus for the task slug + the command that starts the
  workflow (e.g. `auto search search "<slug> new-task" --scope sessions`). Then render it
  (`auto search session get <id>`).
- **Confirm it's the right session.** The top content hit is often the *execution* or *review*
  session, not the one that did the work — they mention the task more. Look for the actual
  workflow invocation and genuine operator turns. A task may also be worked across several
  sessions, or a `/command` may have been abandoned and redirected.
- **Filter the boilerplate.** Transcripts interleave machine-injected text with real human
  turns. Drop `<local-command…>`, `<command-name>…`, "Base directory for this skill", and
  `<teammate-message>` blocks; keep the substantive asks and answers.

### Requirements-derived (faster, reliable)

When the thread is fragmented or buried, author the prompt + the load-bearing `human_turns`
from the task's own **requirements / solution docs** in the target repo — those *are* the
captured intent. Pull the real steering decisions (e.g. an explicit "use approach X, not Y —
it supersedes the original plan"). Caveat: mild hindsight bias (you're authoring from the
outcome), but the *same* fixture drives both arms, so the comparison stays fair.

## Scale gradually

Start with **1–2 fixtures** and prove the full loop (build → run → capture → metrics) before
authoring a dozen. The first real replay is where the fiddly contamination/checkout/auth bugs
live; find them cheap.

## A note on the simulated human

For interactive skills, the fixture's `human_turns` stand in for the operator. Hand-authored
turns are the practical start. They must **drive the workflow's gates themselves** if the
skill is gated (e.g. send the next-stage command when the workflow hard-stops), and should
forbid the agent from using interactive menus the harness can't answer — instruct it to
proceed autonomously or ask in plain text. A later upgrade is a simulated-user *agent* that
answers from an extracted intent corpus, but don't build that before the basic loop works.
