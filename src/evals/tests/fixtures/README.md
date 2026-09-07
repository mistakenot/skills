# Recorded evidence

`live-stream.jsonl` is a real `--output-format stream-json` transcript, captured
from a live clean-room run of the walking skeleton on 2026-09-04 (Claude Code
2.1.260, `claude-sonnet-4-6`, prompt "what is 2+2?"). It is frozen on purpose.

It has three jobs:

* it is the ground truth the stub runner's canned transcript is checked against
  (`test_stream_parity.py`), so the offline lane cannot quietly drift into a
  simplified shape the invocation parser would never meet in production;
* it stands in for the agent process in the live-runner arm of
  `test_runner_seam.py`, so the live code path is exercised against output a real
  agent actually produced.

* it is the invocation parser's negative control (`test_invocation.py`): a real
  transcript that contains no `Skill` call at all, so "reports NOT INVOKED" is
  checked against output an agent genuinely produced rather than against a stream
  hand-shaped to fail.

Re-record it only when the CLI's stream shape genuinely changes, and update the
stub in the same commit — a parity failure is the signal, not the problem.

## The two arms of a real `instructed` run

`live-none-instructed-stream.jsonl` and `live-worktree-instructed-stream.jsonl`
are the `none` and `WORKTREE` arms of one real run of the rich-doc scenario
(`--invoke instructed`, 2026-09-04, run `20260904-141016-aef7180`). They are the
ground truth for `test_failed_skill_call.py`, and they exist because the stub
could not be trusted to produce them:

* the `none` arm contains a **`Skill` call that was refused** —
  `<tool_use_error>Unknown skill: rich-doc</tool_use_error>` — the shape the stub
  did not model and the detector therefore read as an invocation
  (`skills-7k7.11`);
* the `WORKTREE` arm is the same prompt with the skill installed, and made **zero
  `Read` calls into the skill directory**: the `Skill` tool opens `SKILL.md`
  itself, and the only other evidence in the transcript is a `Bash` line running
  `config/skills/rich-doc/scripts/pd-lint.mjs`.

Both are kept whole rather than trimmed. A trimmed transcript is a transcript
someone chose the contents of, which is the failure these files were added to
prevent.
