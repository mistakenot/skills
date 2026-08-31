# Scanning output across all workers

Search recent output across every worker pane in a session at once, rather
than reading one pane at a time (see [read-output.md](read-output.md) for the
single-pane form).

```
Usage: ntm grep <pattern> [session-name] [flags]
```

The session name is a **positional argument**, not a flag:

```bash
ntm grep '(execute-task|phase|Phase|PR |error|stuck|permission|Task complete)' <session> --cc -i
```

Flags:

| Flag         | Meaning                                    |
| ------------ | ------------------------------------------- |
| `--cc`       | restrict the scan to Claude panes only — Codex and OpenCode panes are not searched |
| `-i`         | case-insensitive match                      |
| `-C`/`-A`/`-B` | context lines (around/after/before a match, grep-style) |
| `-n N`       | search only the last N lines                |
| `--all`      | search across all sessions, not just the one named |

Source: `ntm grep --help` (verified against the installed binary, 2026-08-24),
cross-checked against the example usage in
`src/planning-workflow/skills/status-report/SKILL.md:48`.
