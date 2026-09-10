# Recorded member transcripts

Verbatim stdout / stderr / exit code (or a `timeout` marker) captured from the
real CLIs during consult-the-council's first live runs on 2026-09-10, on
claude 2.1.265, codex-cli 0.151.0, gemini 0.34.0, opencode 1.15.13, grok 0.2.60.
`answer` is what codex wrote to its `-o FILE`.

They exist so the stub is not kinder than reality: every case is a shape a CLI
actually produced, including the ones that broke the first council. The tests
replay each through the script's real classification path
(`--runner replay`, `COUNCIL_REPLAY_DIR`) and pin the status and answer it must
yield. When a CLI changes its output shape, record the new transcript here and
update the expectation; do not edit these by hand.

| Case | What the CLI did | Expected |
| ---- | ---------------- | -------- |
| claude-variadic-prompt-swallowed | `--add-dir DIR PROMPT`: prompt parsed as a directory, print mode refused | error |
| claude-ok | plan-mode answer (before the switch to a tool allowlist) | ok |
| codex-echoes-auth-marker | rc 0; session log on stderr echoes "not logged in" from a repo file it read | ok, not auth |
| opencode-json-stream | `--format json` event stream; answer in `text` events | ok |
| opencode-default-format-drops-answer | default format, stdout not a TTY: banner only, no answer | error |
| opencode-external-dir-rejected | no `--dir`: every repo read auto-rejected as external | error |
| gemini-api-key-missing | selectedType api-key, no key exported: exit 41 | auth |
| grok-device-code-hang | expired token: device-code login, never returns | auth |
