#!/usr/bin/env bash
# Seed the workspace with a pinned checkout of simonw/datasette.
#
# Fetched as a tarball rather than cloned. History is what makes a repo slow to
# fetch and nothing in this task reads it: the tarball is ~1MB and 329 files,
# and lands in well under a second against a clone of the full history. It also
# pins harder — there is no history in the tree for an agent to mine, and no
# ref to drift, so the sha below is the whole story.
#
# The sha is literal on purpose. `check_pins` in scenarios.py fails this file if
# it ever names a branch: at this commit datasette has no parquet support of any
# kind, and a floating fetch that picked up an upstream implementation would
# quietly hand the agent the answer to the task.
#
# Extracted into a subdirectory, never into the workspace root: the workspace
# itself must not become a git repo or look like one, or the clean-room canaries
# reject the cell (canaries.py, canary 2).
set -euo pipefail

SHA=bdc973174096cae350ddaa733a10ed8b3ffd970b

mkdir -p datasette
curl -fsSL "https://codeload.github.com/simonw/datasette/tar.gz/$SHA" \
  | tar -xz --strip-components=1 -C datasette

test -f datasette/datasette/hookspecs.py
