.PHONY: compile lint check install

# Compiles skill source files from ./src/ into ./skills/ output.
# Run after editing any skill source in ./src/.
compile:
	python3 src/compile.py

# Compiles then installs all skills into claude-code and codex agents.
# Run to publish updated skills to agents after making changes.
install: compile
	npx skills install ./skills -s '*' -a claude-code codex -y

# Lints all skills for structural and content issues.
# Run before committing to catch problems early.
lint:
	autoskill lint

# Runs compile + lint as a pre-commit check.
# Run before pushing to ensure everything is valid.
check: compile lint
