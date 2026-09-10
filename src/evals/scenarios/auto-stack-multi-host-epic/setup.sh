#!/usr/bin/env bash
# Seed the workspace with a pinned checkout of mistakenot/auto-stack, at the
# commit immediately before epic 003 (multi-host architecture) was planned.
#
# The task is epic-sized: plan a multi-task initiative over a real monorepo.
# The sha is the parent of the commit that added docs/epics/003-*/epic.html,
# so the tree holds everything the real epic was planned from (auto-ui,
# auto-watch, the bus spec, the project registry, tasks up to 026) and nothing
# of the epic or its ten tasks. The human-authored epic on main, and the
# feedback.md of the tasks that implemented it, are the ground truth a reader
# compares the arms against — see prompt.md.
#
# Fetched as a tarball, extracted into a subdirectory (the workspace root must
# not be or look like a git repo — canaries.py, canary 2).
#
# The checkout carries its own agent skills under .agents/ and .claude/ —
# including copies of new-task, review-task and planning-doc — and sub-projects
# carry .claude/ dirs of their own. Left in place they are discovered as
# project skills inside the workspace and contaminate both arms, so every
# such directory is removed. The repo's CLAUDE.md / AGENTS.md stay: an
# epic planner legitimately reads project instructions, and the sub-project
# table in them is real context. One section is stripped from both: the rule
# that questions must go through AskUserQuestion, which a headless run cannot
# honour and which would push the agent to stop rather than record questions.
set -euo pipefail

SHA=3f234f0b132bf9704dc158a83603e715d897aaae

mkdir -p auto-stack
curl -fsSL "https://codeload.github.com/mistakenot/auto-stack/tar.gz/$SHA" \
  | tar -xz --strip-components=1 -C auto-stack

# The fixture's own agent config, freshly extracted above, at every depth
# (sub-projects carry their own .claude/). Plain `skills/` source dirs stay:
# Claude Code discovers .claude/skills and .agents/skills, not bare folders.
find auto-stack -type d \( -name .agents -o -name .claude \) -prune -exec rm -rf {} +

# Drop the "## Agent Interaction Rules" section (up to the next "## " heading).
for f in auto-stack/CLAUDE.md auto-stack/AGENTS.md; do
  awk '
    /^## Agent Interaction Rules/ { skip = 1; next }
    skip && /^## / { skip = 0 }
    !skip { print }
  ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

test -f auto-stack/docs/auto-bus-spec.md
test -d auto-stack/auto-ui
test -d auto-stack/auto-watch
test -d auto-stack/docs/epics
test ! -e auto-stack/docs/epics/003-multi-host-architecture
