#!/usr/bin/env bash
# Release pd-components: bump version, build, commit, tag, push, purge the CDN
# cache, and verify the tag serves the new bundle.
#
# Usage:  bash pd-components/release.sh <version>     # e.g. 0.5.0
#    or:  make release VERSION=0.5.0
#
# Why this exists (the two gotchas it bakes in):
#   1. jsDelivr serves tags IMMUTABLY — you must BUMP the version, not just
#      rebuild, or no doc ever sees the change. The preflight refuses to reuse
#      an existing tag.
#   2. The planning-doc skill pins its llms.txt fetch (and pd.min.js) to the
#      release tag via {{ pd-version }}. This recompiles the skill so that pin
#      tracks the new tag, and commits it in the release. Consumers pick it up
#      by reinstalling the skill — there is no @main path to cache-bust.

set -euo pipefail

REPO="mistakenot/skills"
VERSION="${1:-}"
cd "$(dirname "$0")"  # -> pd-components/
ROOT="$(git rev-parse --show-toplevel)"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: release.sh <version>   (semver, e.g. 0.5.0)"; exit 1
fi
TAG="pd-v$VERSION"

# --- preflight ---------------------------------------------------------------
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "✗ not on main"; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo "✗ working tree not clean — commit or stash first"; exit 1; }
if git rev-parse "$TAG" >/dev/null 2>&1 || git ls-remote --tags origin "$TAG" 2>/dev/null | grep -q "refs/tags/$TAG$"; then
  echo "✗ tag $TAG already exists. Tags are immutable on the CDN — bump to a new version."; exit 1
fi
git pull --ff-only origin main >/dev/null 2>&1 || { echo "✗ local main is not fast-forward with origin — reconcile first"; exit 1; }

echo "→ releasing $TAG"

# --- bump + build ------------------------------------------------------------
npm version "$VERSION" --no-git-tag-version >/dev/null
npm run build
grep -q "pd-components v$VERSION" dist/pd.min.js || { echo "✗ build did not stamp v$VERSION into the bundle"; exit 1; }

# --- recompile skills so the {{ pd-version }} pin tracks the new tag ----------
(cd "$ROOT" && uv run --no-dev python src/compile.py >/dev/null)
grep -q "skills@$TAG/pd-components/dist/llms.txt" "$ROOT/skills/planning-doc/SKILL.md" \
  || { echo "✗ compiled skill did not pin llms.txt to $TAG"; exit 1; }

# --- commit + tag + push -----------------------------------------------------
git -C "$ROOT" add pd-components/package.json pd-components/package-lock.json \
  pd-components/dist/pd.min.js pd-components/dist/llms.txt skills/
git -C "$ROOT" commit -q -m "Release pd-components $TAG"
git -C "$ROOT" tag "$TAG"
git -C "$ROOT" push origin main "$TAG"

# --- verify the immutable tag serves the new bundle --------------------------
if curl -sS -m 30 "https://cdn.jsdelivr.net/gh/$REPO@$TAG/pd-components/dist/pd.min.js" | grep -q "pd-components v$VERSION"; then
  echo "✓ released $TAG — CDN serving v$VERSION; new docs will pin it"
else
  echo "⚠ $TAG pushed, but the CDN isn't serving v$VERSION yet (give it a minute, then re-check)"
fi
