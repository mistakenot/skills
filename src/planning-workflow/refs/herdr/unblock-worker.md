# Clearing a `blocked` worker (herdr)

A worker whose `agent_status` is `blocked` is sitting at a dialog — a Claude
Code `AskUserQuestion` picker, an approval prompt, a startup interstitial. Only
**interactive input** clears it: `agent prompt` is refused by design
(`agent_blocked`), and nothing else the worker does will move it. Verified live
against herdr 0.8.2 and Claude Code 2.1.252.

## Decide first: answer it, or hand it to a human

Read the pane (`references/herdr/read-output.md`) and work out what it is asking.

- **The answer is settled** — by the task docs, the user's prompt, or the
  workflow (e.g. a safe interstitial choice) — answer it as below.
- **The decision is load-bearing** and not yours to make — a schema change, a
  destructive step, a scope call — escalate to the user with the question
  verbatim. A worker that stopped to ask about one of these was right to stop.
- **Never send `esc`.** The picker footer offers it as *cancel*: it discards the
  question rather than answering it, and the worker has usually done real work
  to reach that point.

## The recipe

```bash
herdr agent read  <name>                 # find the ❯ marker: which option is selected
herdr pane send-keys <PANE_ID> down      # or up — ONE press at a time
herdr agent read  <name> | grep '❯'      # verify the marker moved, after EVERY press
herdr pane send-keys <PANE_ID> return    # 'return', not 'enter'
herdr agent get   <name>                 # confirm: blocked -> working
```

`<PANE_ID>` comes from `agent list` / `agent get` (`pane_id`, e.g. `w3:p1`) —
see `references/herdr/list-workers.md`.

Two things here are non-obvious and both cost real time when got wrong:

1. **`pane send-keys <PANE_ID>`, not `agent send-keys <NAME>`.** The
   agent-level command returns `{"result":{"type":"ok"}}` and delivers nothing
   to the picker. `agent focus` first does not help — focus is not the problem.
2. **`return`, not `enter`.** `enter` is also accepted with `ok` and also does
   nothing — at either level. Navigation (`up`/`down`) works under both
   spellings; only the confirm key is fussy.

`{"type":"ok"}` means herdr validated the key names, **not** that the dialog
received them. The only evidence of delivery is a re-read showing the marker
moved or the dialog gone.

## What does not work

| Attempt | Result |
| :-- | :-- |
| `agent prompt <name> "option 1"` | `agent_blocked` — refused loudly, before writing any input |
| `agent send-keys <name> enter` | `ok`, nothing happens |
| `agent send-keys <name> 1` | `ok`, nothing happens — the picker does not take option numbers |
| `agent focus <name>` then `agent send-keys` | `ok`, nothing happens |
| `pane send-keys <PANE_ID> enter` | `ok`, nothing happens |

## Diagnose before you flail

Send a **navigation** key and check whether the `❯` marker moved. It is
non-destructive and separates "keys are not arriving" from "this key name is
wrong":

```bash
herdr agent read <name> | grep -E '^\s*❯?\s*[1-4]\.'   # before
herdr pane send-keys <PANE_ID> down
herdr agent read <name> | grep -E '^\s*❯?\s*[1-4]\.'   # after — did ❯ move?
```

Marker moved ⇒ keys land; only the confirm key is in question (use `return`).
Marker did not move ⇒ you are on the wrong command (agent-level instead of
pane-level).

## One press at a time

Do **not** batch presses (`down down return`). In one observed run the marker
ended up two positions from where a single press should have left it —
plausibly earlier agent-level presses arriving late, or a boundary wrap. Send
one key, re-read, repeat. Two seconds per press removes all guessing. There is
no shortcut via option numbers.

## Fallback

If the recipe does not clear it, hand it to a human: `herdr agent attach
<name>`, answer, detach. Do not keep sending keys into a dialog you cannot see
responding.

## Avoiding it in the first place

A blocked background worker is a hard stop until a correctly formed pane
keypress or a human arrives. When dispatching unattended work whose prompt you
control, tell the worker to proceed on its recommended answer and record the
question rather than ask — the pattern
`/{{ skill:new-task-quick }}` uses for gating questions. Reserve blocking for
decisions that are genuinely load-bearing.
