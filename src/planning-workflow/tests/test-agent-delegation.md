# Test: agent delegation under herdr (Claude Code + Codex)

A self-contained procedure verifying that herdr can **spawn, verify, prompt,
and reap** both agent kinds in this environment. It builds a throwaway repo and
an isolated herdr session, runs a Ping/Pong on each agent, exercises the failure
modes the delegate skills are written around, and tears everything down.

Companion references: the per-operation guides in [../refs/herdr/](../refs/herdr/)
(compiled into the delegate-family skills as `references/herdr/<operation>.md`)
and [../refs/agent-conventions.md](../refs/agent-conventions.md).

**Pass criteria:**

1. Both agents come up in a **no-permissions-required** mode, verified from
   process argv — not from the status line.
2. Both answer a prompt sent with `agent prompt`.
3. Both answer a prompt passed as launch argv.
4. `agent wait` returns without `--until idle`.
5. Everything is reaped, including the git worktrees.

## 0. Preconditions

```bash
herdr --version            # must be >= 0.8.2
herdr integration status   # claude and codex must be "current"
command -v claude codex
```

Stop if herdr is older than 0.8.2 — `agent start --kind`, `agent prompt`, and
blocked-startup detection do not exist before it, and this procedure tests
nothing meaningful without them.

## 1. Isolated server

Run against a **named test session**, never the user's live one. Start it from a
plain terminal, **not from inside a coding-agent session** — a server started
inside one leaks that session's environment (e.g. `CLAUDE_CODE_CHILD_SESSION`)
into every pane it later creates, which silently changes the launched agent's
default permission mode and disables transcript saving.

```bash
export HERDR_CONFIG_PATH=/tmp/herdr-deltest/config.toml
mkdir -p /tmp/herdr-deltest
nohup herdr --session deltest server >/tmp/herdr-deltest/server.log 2>&1 &
H="herdr --session deltest"
$H status          # expect version 0.8.2+, status running
```

## 2. Throwaway repo and a worktree worker

```bash
R=/tmp/herdr-deltest/repo
mkdir -p $R && cd $R && git init -q -b main && echo hi > README.md
git add -A && git -c user.email=t@t -c user.name=t commit -qm init

J=$($H worktree create --cwd $R --branch task/001 --base main --label deltest --no-focus)
WS=$(echo "$J" | jq -r .result.workspace.workspace_id)
P1=$(echo "$J" | jq -r .result.root_pane.pane_id)
```

## 3. Arm A — Claude Code, prompted with `agent prompt`

```bash
$H agent start t-claude --kind claude --pane "$P1" --timeout 90000 \
  -- --dangerously-skip-permissions
```

If this returns `agent_not_ready`, the agent hit a startup interstitial (most
likely the folder-trust prompt on a brand-new directory). Read the pane and
answer it **with the specific key, never a bare `enter`**:

```bash
$H pane read "$P1" --source visible
$H agent send-keys t-claude down enter    # "Yes, I trust this folder"
$H agent wait t-claude --timeout 60000
```

**Check 1 — permission mode from argv, not the status line:**

```bash
$H pane process-info --pane "$P1" \
  | jq -r '.result.process_info.foreground_processes[].cmdline'
# must contain --dangerously-skip-permissions
```

**Check 2 — prompt round trip:**

```bash
$H agent prompt t-claude "Reply with exactly: PONG_CLAUDE" --wait --timeout 120000
$H agent read t-claude --source recent-unwrapped --lines 60 | grep PONG_CLAUDE
```

Note `agent read` prints **raw text** — do not pipe it through
`jq .result.read.text` (that was the 0.7.x envelope).

## 4. Arm B — Codex, prompted with `agent prompt`

```bash
P2=$($H pane split "$P1" --direction down --cwd "$(git -C $R worktree list --porcelain | awk '/task-001/{print $2}')" --no-focus | jq -r .result.pane.pane_id)
$H agent start t-codex --kind codex --pane "$P2" --timeout 90000 \
  -- --dangerously-bypass-approvals-and-sandbox
```

Codex has more first-run interstitials than Claude Code: a directory-trust
prompt, an "Update available" prompt whose **default is Update now** (which runs
`npm install` and drops the pane to a shell), and a "Hooks need review" prompt
triggered by herdr's own agent-state hook. Answer each explicitly — `1 enter`,
`3 enter`, `2 enter` respectively — never a bare `enter`.

```bash
$H pane process-info --pane "$P2" \
  | jq -r '.result.process_info.foreground_processes[].cmdline'
# BOTH the node launcher and the native binary appear; both must carry
# --dangerously-bypass-approvals-and-sandbox

$H agent prompt t-codex "Reply with exactly: PONG_CODEX" --wait --timeout 180000
$H agent read t-codex --source recent-unwrapped --lines 60 | grep PONG_CODEX
```

## 5. Arm C — kickoff prompt as launch argv

The dispatch path the delegate skills prefer, because it has no separate
text-delivery step:

```bash
P3=$($H pane split "$P1" --direction right --no-focus | jq -r .result.pane.pane_id)
P4=$($H pane split "$P2" --direction right --no-focus | jq -r .result.pane.pane_id)

$H agent start t-argv-cc --kind claude --pane "$P3" --timeout 90000 \
  -- --dangerously-skip-permissions "Reply with exactly: ARGV_CLAUDE"
$H agent start t-argv-cx --kind codex --pane "$P4" --timeout 90000 \
  -- --dangerously-bypass-approvals-and-sandbox "Reply with exactly: ARGV_CODEX"

$H agent read t-argv-cc --source recent-unwrapped --lines 60 | grep ARGV_CLAUDE
$H agent read t-argv-cx --source recent-unwrapped --lines 60 | grep ARGV_CODEX
```

## 6. Negative checks — the failure modes the skills guard against

**`--until idle` must be avoided.** A CLI-driven worker settles at `done`, not
`idle`, because `idle` additionally requires the tab to have been seen in the
focused UI and CLI reads do not mark it seen:

```bash
$H agent wait t-claude --until idle --timeout 15000   # EXPECT: timeout error
$H agent wait t-claude --timeout 15000                # EXPECT: returns immediately
```

**A bare launch lands in manual mode and cannot be rescued.**

```bash
P5=$($H pane split "$P3" --direction down --no-focus | jq -r .result.pane.pane_id)
$H agent start t-bare --kind claude --pane "$P5" --timeout 90000
$H pane process-info --pane "$P5" \
  | jq -r '.result.process_info.foreground_processes[].cmdline'
# EXPECT: bare "claude" with no permission flag
$H pane read "$P5" --source visible | tail -3
# EXPECT: "⏸ manual mode on"
$H agent send-keys t-bare shift+tab; $H agent send-keys t-bare shift+tab
$H pane read "$P5" --source visible | tail -3
# EXPECT: still "manual mode on" — shift+tab cannot reach bypass
```

**Key names are herdr's, not tmux's.** `ctrl+u` clears the input box; `C-u` is
silently ignored, so a clear step written in tmux notation does nothing and the
next text appends to whatever was already there.

**`pane wait-output` matches your own echoed prompt.** Waiting for a token you
just sent matches the input line, not the reply — match on something only the
agent's output can contain, or wait on status instead.

## 7. Teardown

`workspace close` does **not** remove the git worktree — remove it first, while
the workspace still exists to identify it:

```bash
$H worktree remove --workspace "$WS" --force
$H workspace close "$WS"
$H session stop deltest
git -C $R worktree prune
```

Confirm nothing is left:

```bash
git -C $R worktree list      # only the primary checkout
$H status                    # server no longer running
```
