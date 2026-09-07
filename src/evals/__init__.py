"""Contained A/B harness for skill versions.

`--n` trials per arm (default one). `--arm` is repeatable and takes three
forms — `none`, `WORKTREE`, or a git ref — and each arm gets its own clean room
and its own `runs/<run-id>/<arm>/` subtree; arms never share a workspace. See
`paths.py` for the repo/run layout, `canaries.py` for the isolation assertions,
`arms.py` for arm resolution and the per-arm `manifest.json` provenance,
`cell.py` for the clean-room agent invocation and `runners.py` for the
live/stub seam that makes everything except the agent's judgment testable
offline (`evals run ... --runner stub`).

`scenarios.py` holds the other half of a run: the task. A scenario is a
directory (`prompt.md`, optional `setup.sh` and `fixture/`) that can prepare a
real workspace — pinned to a sha, checked rather than trusted, and fetched once
per scenario into `cache/` rather than once per cell. See `scenarios/README.md`.

`manifest.py` and `manage.py` are the run-management half: a run-level
`manifest.json` recording what was compared (pointing at the per-arm records
rather than copying them), and `evals list` / `show` / `clean` over the runs
that accumulate. `show` is the everyday entry point after a run finishes.

`invocation.py` is the harness's only automated check: it reads the `Skill`,
`Read` and `Bash` tool calls out of `stream.jsonl` to say whether the skill
actually fired and what it opened. Everything else fails loudly; a skill that
silently never loaded produces two plausible outputs and no comparison.
"""
