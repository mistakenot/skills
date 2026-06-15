.PHONY: compile lint check install pd-components pd-test test eval-assurance

# Compiles skill source files from ./src/ into ./skills/ output.
# Run after editing any skill source in ./src/.
compile:
	uv run --no-dev python src/compile.py

# Compiles then installs all skills into claude-code and codex agents.
# Run to publish updated skills to agents after making changes.
install: compile
	npx skills install ./skills -s '*' -a claude-code codex -y

# Builds the pd-components bundle + llms.txt consumed by the planning-doc skill.
# Run after editing pd-components/src/. See pd-components/README.md for the release/tag flow.
pd-components:
	cd pd-components && npm install && npm run build

# Runs browser regression tests for pd-components using agent-browser.
# Run after editing pd-components/src/ to verify nothing broke.
pd-test:
	bash pd-components/tests/run.sh

# Lints all skills for structural and content issues.
# Run before committing to catch problems early.
lint:
	autoskill lint

# Runs compile + lint as a pre-commit check.
# Run before pushing to ensure everything is valid.
check: compile lint

# Runs pytest for assurance module tests.
# Run to validate compiler extensions and card schema.
test:
	uv run pytest src/assurance/tests/

# Runs the two-arm assurance eval harness.
# Run after compiling to produce a with-vs-without comparison report.
eval-assurance: compile
	bash src/assurance/evals/run.sh
