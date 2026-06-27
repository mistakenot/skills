#!/usr/bin/env bash
# build.sh — compile one eval arm into a runnable worktree (planning-eval).  See README.md.
#
# Borrows auto-eval v1's `build` step (worktree at an immutable start SHA, clean history),
# but the "setup" is fixed: overlay the arm's planning skills into the worktree so the
# agent under test sees exactly that workflow (v2 or v3) and nothing of the operator's.
#
# NTM derives a session's cwd from `<projects_base>/<session_name>`, and projects_base is
# /home/vscode/src — so the worktree MUST be created at /home/vscode/src/<session_name>.
#
# Usage: build.sh <target_repo> <start_sha> <arm_skills_dir> <session_name>
set -euo pipefail

TARGET_REPO="$1"     # e.g. /home/vscode/src/auto-stack
START_SHA="$2"       # immutable SHA the agent starts from (NOT a branch/HEAD)
ARM_SKILLS_DIR="$3"  # dir of skills to overlay (the arm under test), e.g. skills/ subset
SESSION="$4"         # session name == worktree dirname under projects_base
PROJECTS_BASE="${NTM_PROJECTS_BASE:-/home/vscode/src}"
WORKTREE="$PROJECTS_BASE/$SESSION"

case "$START_SHA" in
  HEAD|main|master) echo "ERROR: start SHA must be immutable, got '$START_SHA'" >&2; exit 2;;
esac

if [ -e "$WORKTREE" ]; then
  echo "ERROR: worktree path already exists: $WORKTREE" >&2; exit 2
fi

# Disable the target repo's git hooks for all eval git ops: a post-checkout/pre-commit hook
# from a *different* commit than the one we check out will fail and is irrelevant to the eval.
GIT="git -c core.hooksPath=/dev/null"

echo "[build] worktree $WORKTREE @ ${START_SHA:0:12} from $TARGET_REPO"
$GIT -C "$TARGET_REPO" worktree add --detach "$WORKTREE" "$START_SHA" >/dev/null

# Clean arm boundary: REPLACE the worktree's skills with exactly the arm's set, so the two
# arms differ only by installed workflow (not by a mix of the target repo's own skills).
# Project CLAUDE.md / AGENTS.md are left intact — that's shared project context, not the
# variable under test.
SKILLS_DIR="$WORKTREE/.claude/skills"
if [ -e "$SKILLS_DIR" ]; then
  echo "[build] removing target repo's existing skills ($(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 | wc -l) entries)"
  rm -rf "$SKILLS_DIR"
fi
echo "[build] installing arm '$(basename "$ARM_SKILLS_DIR")' skills -> .claude/skills/"
mkdir -p "$SKILLS_DIR"
cp -R "$ARM_SKILLS_DIR"/. "$SKILLS_DIR/"
echo "[build] arm skill count: $(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l)"

# Clean history: squash the overlay onto the start commit so `git log` shows no eval
# scaffolding to the agent.
$GIT -C "$WORKTREE" add -A >/dev/null
$GIT -C "$WORKTREE" -c user.name=eval -c user.email=eval@local \
    commit --amend --no-edit >/dev/null 2>&1 || \
  $GIT -C "$WORKTREE" -c user.name=eval -c user.email=eval@local \
    commit -m "eval: install arm skills" >/dev/null

echo "$WORKTREE"
