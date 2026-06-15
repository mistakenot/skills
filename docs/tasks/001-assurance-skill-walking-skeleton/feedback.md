# Feedback: Task 001

## Problems faced
1. `test_real_module_compiles` used the real `src/` dir as `src_dir`, causing `_generate_install_script` to clobber the repo's `install.sh` with only the assurance module — caught by the independent PR reviewer, not by the phase D subagent that wrote the test.
2. Main diverged during execution (beta-planning module + install.sh fix landed), requiring a rebase with merge conflicts in `src/compile.py` and `install.sh`.

## Reflections
- The coordinator-subagent pattern worked well for phases A-D (serial A→B, parallel C∥D). Phase E was the largest and most complex — a single subagent handled it cleanly.
- The independent PR review caught real bugs the implementation subagents missed. The `install.sh` clobbering bug was subtle: tests passed, but left the working tree corrupted. Running a cold reviewer against the PR is worth the cost.
- Rebase conflicts were straightforward because the plan correctly identified which files this task touches vs what's out of scope.

## Useful context
- The `docs/headless-claude-cli-evals.md` clean-room recipe was essential for the eval harness — the spike work paid off.
- The nested `tmp_path/repo/src` layout for tests (to contain `install.sh` side effects) is a pattern worth reusing for any test that calls `compile()`.
