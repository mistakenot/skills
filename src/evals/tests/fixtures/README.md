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
