#!/usr/bin/env bash
# build.sh — compile one eval arm into a runnable worktree (planning-eval, hacked v1).
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

echo "[build] worktree $WORKTREE @ ${START_SHA:0:12} from $TARGET_REPO"
git -C "$TARGET_REPO" worktree add --detach "$WORKTREE" "$START_SHA" >/dev/null

echo "[build] overlay arm skills from $ARM_SKILLS_DIR -> .claude/skills/"
mkdir -p "$WORKTREE/.claude/skills"
cp -R "$ARM_SKILLS_DIR"/. "$WORKTREE/.claude/skills/"

# Clean history: squash the overlay onto the start commit so `git log` shows no eval
# scaffolding to the agent.
git -C "$WORKTREE" add -A >/dev/null
git -C "$WORKTREE" -c user.name=eval -c user.email=eval@local \
    commit --amend --no-edit >/dev/null 2>&1 || \
  git -C "$WORKTREE" -c user.name=eval -c user.email=eval@local \
    commit -m "eval: overlay arm skills" >/dev/null

echo "$WORKTREE"
