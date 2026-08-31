# Test: agent delegation across Claude Code, Codex, and OpenCode

A self-contained procedure an agent can follow to verify that `ntm` can
discover, send to, and clear **all three** coding-agent CLIs in this
environment. It sets up a throwaway session with one of each, runs a Ping/Pong
on every agent, clears them, and tears everything down.

Companion references: the per-operation ntm guides in [../refs/ntm/](../refs/ntm/)
(compiled into the delegate-family skills as `references/ntm/<operation>.md`), and
[../refs/agent-conventions.md](../refs/agent-conventions.md) for the per-CLI send
and clear semantics this procedure exercises.

> This procedure covers the **ntm** runner only. The herdr equivalent has not
> been written; see [../refs/herdr/](../refs/herdr/) for its command surface.

**Pass criteria:** each of the three agents returns `Pong` to a Ping, and each
returns to a clean prompt after `/clear`. Tear down only after this is
confirmed.

Use a dedicated session name so nothing else is touched. Throughout, `$S` is the
test session name and `$DIR` its project directory.

```bash
S=ntm-deltest
DIR="$(ntm config get projects_base)/$S"
```

## 0. Preconditions

Confirm all three CLIs are installed (look for Claude Code, Codex, and an
`opencode` binary on PATH):

```bash
ntm deps -v
command -v claude codex opencode
```

If any is missing, stop — the corresponding arm cannot be tested.

## 1. Setup — spawn one of each agent

`ntm spawn` requires the project directory to exist. Create it, then spawn one
Claude Code (`--cc`), one Codex (`--cod`), and one OpenCode (`--oc`):

```bash
mkdir -p "$DIR" && git -C "$DIR" init -q
ntm spawn "$S" --cc=1 --cod=1 --oc=1 --no-cass-context
```

Confirm the panes came up with the expected types:

```bash
ntm status "$S" --json | jq '.panes[] | {index, type, command}'
```

Record each agent's pane index from `.index` — **do not hard-code indices**,
resolve them. Resolve by `.command`, **not `.type`**: `.type` is derived from the
pane title and is unreliable — an OpenCode pane reports `type:"user"` for many
seconds after spawn (until it first outputs), and a pane that has dropped back to
a shell keeps its stale `type`. `.command` reflects the live process:

```bash
CC=$(ntm status "$S" --json  | jq -r '.panes[] | select(.command=="claude")   | .index')
COD=$(ntm status "$S" --json | jq -r '.panes[] | select(.command=="node")     | .index')  # Codex runs under node
OC=$(ntm status "$S" --json  | jq -r '.panes[] | select(.command=="opencode") | .index')
echo "CC=$CC COD=$COD OC=$OC"   # all three must be non-empty
```

If any is empty, an agent hasn't finished launching (or has exited) — wait a few
seconds and re-run, and inspect the pane (`ntm copy "$S":<index> --last 20
--quiet --output /dev/stdout`).

> **Codex launch interstitials.** Codex may open with a blocking prompt that a
> bare Enter resolves the wrong way:
> - *"Update available… 1. Update now / 2. Skip"* — Enter picks **Update now**,
>   which runs `npm install` and **exits Codex to a shell**, swallowing your
>   first send. Keep the `codex` CLI up to date to avoid it, or dismiss with
>   the non-default choice: `ntm send "$S" --pane=$COD '2'`.
> - *"Do you trust the contents of this directory?"* on a fresh dir (real
>   delegation targets are pre-authorized) — dismiss with `ntm send "$S"
>   --pane=$COD '1'`.
>
> After dismissing, re-resolve `COD` (above) and confirm `.command=="node"`
> before pinging. Claude Code and OpenCode have no such launch gates here.

## 2. Ping/Pong — confirm each agent responds

Send the same Ping to each agent by pane index (the universal path that also
works for OpenCode, which has no type filter). `--no-cass-check` skips the CASS
duplicate-check so an unattended run can't block on its confirmation prompt:

```bash
for P in $CC $COD $OC; do
  ntm send "$S" --pane=$P --no-cass-check 'Reply with exactly one word: Pong'
done
sleep 12
```

Verify each pane shows `Pong`:

```bash
for P in $CC $COD $OC; do
  echo "=== pane $P ==="
  ntm copy "$S":$P --last 30 --quiet --output /dev/stdout | grep -i pong || echo "NO PONG YET"
done
```

OpenCode renders its reply lower in the pane and is not tracked by
`ntm --robot-wait`; if it shows "NO PONG YET", wait a few seconds and re-capture
with a larger `--last`, or send it with acknowledgement instead:

```bash
ntm --robot-send="$S" --panes=$OC --msg='Reply with exactly one word: Pong' --track --timeout=50s \
  | jq '.ack.confirmations'
```

**Checkpoint:** all three must show `Pong` before continuing.

## 3. Clear — confirm each agent resets

```bash
for P in $CC $COD $OC; do
  ntm send "$S" --pane=$P --no-cass-check '/clear'
done
sleep 6
for P in $CC $COD $OC; do
  echo "=== pane $P after /clear ==="
  ntm copy "$S":$P --last 16 --quiet --output /dev/stdout
done
```

Expected:

- **Claude Code** — back to the welcome screen, empty `❯` prompt.
- **Codex** — prints token usage and a `codex resume <id>` line; fresh input box.
- **OpenCode** — back to the "Ask anything…" splash.

**Checkpoint:** all three returned to a clean prompt.

## 4. Teardown — always run this

Only tear down once the Ping/Pong and clear checkpoints have passed (or the test
has definitively failed). Kill the session and remove the throwaway directory:

```bash
ntm kill "$S" --force 2>/dev/null || tmux kill-session -t "$S"
ntm list --json | jq -e '.sessions[] | select(.name=="'"$S"'")' >/dev/null \
  && echo "WARNING: session still present" || echo "session removed"
rm -rf "$DIR"
```

Confirm the session is gone (`ntm list --json` no longer lists `$S`) and the
directory is removed. The environment is back to its original state.
