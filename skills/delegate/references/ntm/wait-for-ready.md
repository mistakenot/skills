# Waiting for a worker to become ready

Block until a pane's agent is idle and will accept input.

```bash
ntm --robot-wait=<session> --wait-until=idle --timeout=60s
```

It returns when the agent reports `state: WAITING` (ready). If `robot-wait` is
unavailable, fall back to reading the pane and confirming the `❯` input prompt
is showing — see [read-output.md](read-output.md):

```bash
ntm copy <session>:<index> --last 20 --quiet --output /dev/stdout
```

**`ntm --robot-wait` does not track OpenCode.** Waiting for idle
(`ntm --robot-wait=<session> --wait-until=idle`) reports state for Claude and
Codex only; OpenCode is absent from the result. To confirm OpenCode is ready
or done, either inspect the pane with `ntm copy` (above) or use
`--robot-send … --track` and rely on the delivery acknowledgement (see
[send-prompt.md](send-prompt.md)).
