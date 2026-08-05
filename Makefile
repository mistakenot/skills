.PHONY: compile lint check install pd-components pd-dev pd-test test test-review-stdin eval-assurance release

# Compiles skill source files from ./src/ into ./skills/ output.
# Run after editing any skill source in ./src/.
compile:
	uv run --no-dev python src/compile.py

# Compiles then renders all skills into .claude/skills/ and .agents/skills/.
# Run to publish updated skills to agents after making changes.
install: compile
	auto skill sync --text

# Builds the pd-components bundle + llms.txt consumed by the planning-doc skill.
# Run after editing pd-components/src/. See pd-components/README.md for the release/tag flow.
pd-components:
	cd pd-components && npm install && npm run build

# Releases pd-components: bump version, build, commit, tag, push, purge the CDN
# cache, and verify the tag serves the new bundle. Run `make pd-test` first.
# Usage: make release VERSION=0.5.0
release:
	@test -n "$(VERSION)" || { echo "usage: make release VERSION=x.y.z"; exit 1; }
	bash pd-components/release.sh $(VERSION)

# Starts the pd-components dev server with live reload + tailscale serve on port 8743.
# Open http://localhost:8766 locally or the tailscale URL printed on startup.
pd-dev:
	bash pd-components/dev.sh

# Runs browser regression tests for pd-components using agent-browser.
# Run after editing pd-components/src/ to verify nothing broke.
pd-test:
	bash pd-components/tests/run.sh

# Lints all skills for structural and content issues.
# Run before committing to catch problems early.
lint:
	auto skill lint

# Runs compile + lint as a pre-commit check.
# Run before pushing to ensure everything is valid.
check: compile lint

# Runs pytest for assurance module tests.
# Run to validate compiler extensions and card schema.
test:
	uv run pytest src/assurance/tests/

# Verifies request-codex-review / request-claude-review / request-grok-review
# don't hang on stdin when launched as background reviews. Needs codex + claude
# + grok installed and authed.
# Set SKIP_NEG=1 to skip the ~10s codex negative-control hang.
test-review-stdin: compile
	bash src/planning-workflow/tests/test-background-review-stdin.sh

# Runs the two-arm assurance eval harness.
# Run after compiling to produce a with-vs-without comparison report.
eval-assurance: compile
	bash src/assurance/evals/run.sh
