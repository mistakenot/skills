# Per-agent CLI conventions

How Claude Code, Codex, and OpenCode each behave **in themselves** — process
identity, how they accept text and slash commands, and their differing
`/clear` semantics. This holds regardless of which runner (multiplexer) is
driving the pane. Runner-specific commands, flags, and JSON fields are a
different concern and live in `references/<runner>/` instead — see
[references/worker-pools.md](references/worker-pools.md) and the delegate
skills for how the `runner` variable selects that directory.

For headless (no-pane) CLI delegation — running a review CLI in print mode
from bash and exiting, which is also how Grok is driven — see
[references/headless-delegation.md](references/headless-delegation.md).

## Process identity

Each CLI runs as a distinct process, which is the most reliable way to tell
them apart regardless of runner:

| Agent | Process name |
| ----- | ------------- |
| Claude Code | `claude` |
| OpenCode | `opencode` |
| Codex | `node` — Codex runs under Node, so `node` is its tell |

A pane whose live process is a plain shell (`bash`, etc.) is not a running
agent, whatever a runner's own status label claims — never delegate there.

## Text, slash commands, and `/clear` semantics

Slash commands are not a special protocol — every agent treats them as
literal text typed into its prompt. What `/clear` does differs per agent:

| Agent | `/clear` behaviour | Slash commands / skills |
| ----- | ------------------- | ------------------------ |
| **Claude Code** | Resets context in place; returns to the welcome/empty prompt. | `/clear`, `/<skill>`, `/rename`, any slash command — sent as literal text. |
| **Codex** | Starts a **new** conversation; prints prior token usage and a `codex resume <id>` line. | `/skills` to list, `/model` to switch; send `/<cmd>` as text. |
| **OpenCode** | Returns to the "Ask anything…" splash; context dropped. | Sent as text; an interactive palette also exists (`ctrl+p`), but for automation send the literal command. |

> This table describes each CLI's own in-place `/clear`, for interactive
> human use. **Automated dispatch never relies on it** — `/clear` is
> cooperative: sent to a pane you misread as idle, it doesn't reject or
> no-op, it silently queues behind in-flight work and detonates later. The
> delegate skills always obtain a clean pane a different way (never `/clear`,
> never an in-place restart) — see `references/{{ .runner }}/reset-worker.md`
> and `references/{{ .runner }}/spawn-worker.md`.

## Launch interstitials

Confirm an agent is actually live before the first send. Codex in particular
can show a blocking launch interstitial on a fresh process — e.g. an
*"Update available… 1. Update now / 2. Skip"* prompt, or (first run) a *"Do
you trust this directory?"* prompt. An unattended `Enter` sent as part of
prompt delivery will select the default option (typically "Update now"),
which runs `npm install` and drops the pane back to a shell, swallowing the
message. Before delegating, verify the pane's live process is the agent (not
a shell) and read the pane; if an interstitial is showing, dismiss it with
the **non-default** choice rather than a bare `Enter`. Keeping the agent CLIs
updated avoids the update prompt entirely.
