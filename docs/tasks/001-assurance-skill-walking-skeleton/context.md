# Context: Task 001

Codebase facts grounding the [solution](./solution.md) for the assurance-strategist walking skeleton: how `src/compile.py` works, how a `src/` module is structured, and the eval clean-room recipe already de-risked by the task-001 spike.

## Key Files

### The compiler — `src/compile.py` (344 lines)

- `src/compile.py:19-41` — the DSL. `Ref`/`Skill`/`Module` dataclasses + `ref()`, `skill(name, refs=[])`, `module(name, *skills)` factories. A module's `name` must equal its directory under `src/`.
- `src/compile.py:48-51` — the two directives + size limit:
  - `REF_PATTERN = re.compile(r"^\{\{\s*ref:(.+?)\s*\}\}$", re.MULTILINE)` — inline-expand directive.
  - `REF_LINK_PATTERN = re.compile(r"\[references/(.+?)\]\(references/", re.MULTILINE)` — markdown link to a ref (copied, **not** inlined). This is the AC-1 "linked not inlined" mechanism.
  - `MAX_OUTPUT_CHARS = 15_000`.
- `src/compile.py:54-66` — `_parse_frontmatter(text)`. **Flat key:value only**, no pyyaml, no nesting, no lists. `line.partition(":")` splits on first colon; surrounding quotes stripped. Returns `None` if no frontmatter. → card frontmatter must be flat keys (`pairs-with:` as a comma string, `cost-author:`/`cost-maintain:`/`cost-run:` separate).
- `src/compile.py:79-138` — **Phase 1 validation** (runs before any writes; `sys.exit(1)` on any error). Currently checks: module dir exists, template exists, declared refs exist on disk, frontmatter present with `name`+`description`, and cross-checks template `{{ ref:X }}`/`[references/X]` usage against DSL declarations (lines 119-128: undeclared-but-used = ERROR, declared-but-unused = WARN). **This is the hook point for card-schema validation (AC-3).**
- `src/compile.py:157-163` — render: `replace_ref` reads `refs/<filename>` and `REF_PATTERN.sub` inlines it. **Hook point for the new `{{ index:techniques }}` directive — must run here, before the size check.**
- `src/compile.py:166-170` — size check on the rendered string.
- `src/compile.py:173-187` — output: writes `skills/<name>/SKILL.md`, copies every declared ref to `skills/<name>/references/<filename>` via `shutil.copy2`.
- `src/compile.py:305-348` — `__main__`: 6 modules are **hard-coded** (no glob/auto-discovery) and passed to `compile([...])`. Adding `src/assurance/` requires a new `module("assurance", ...)` declaration appended to that list. `install.sh` is regenerated from this same list (subagent-reported, lines ~211-298), so the new module auto-registers there.

### Module structure (mirror this for `src/assurance/`)

- `src/planning-workflow/` is the representative module: `refs/*.md` (shared, plain markdown, no frontmatter) + `skills/<name>/SKILL.md` (frontmatter `name`+`description`, body links refs via `[references/X](references/X)`).
- `src/ideation/fan-out-user-simulation/evals/evals.json` — precedent: a skill's local support files (e.g. `evals/`) are **not** declared as refs, so the compiler never copies them to `skills/` output. → `src/assurance/evals/` is automatically excluded from compiled output, exactly as the diary requires.
- `src/CLAUDE.md` — documents module conventions and the `{{ ref: }}` directive; will need a note about the new `{{ index:techniques }}` directive.

## Patterns

- **Dependency-free compiler**: no pyyaml, stdlib only; the repo has no `pyproject.toml`/lockfile today and pytest is not installed. New validation/index code stays stdlib-only and parses flat frontmatter. (This task adopts **uv** for python: `pyproject.toml` + `uv.lock`, pytest in a dev group, all python invocations via `uv run` — including the existing `Makefile:6` and `scripts/pre-commit-checks.sh` compile steps. uv 0.10.9 is available.)
- **Declare-everything-validate-everything**: refs are listed explicitly in the DSL, not globbed; every declared ref must be used or it warns. The card index directive must register declared `technique-*.md` refs as "used" to avoid a spurious unused-warning.
- **Validation fails the build with a clear, tagged error** (`[module/skill] ...`). Card errors should follow the same shape and name the card + missing element.
- **`make` targets are thin wrappers**: `compile:` → `python3 src/compile.py` (this task migrates to `uv run --no-dev python src/compile.py`); `lint:` → `autoskill lint`; `check:` → compile + lint. A new `eval-assurance` target follows the same one-line-wrapper pattern.

## Eval clean-room recipe (already de-risked)

The headless-eval isolation question was answered by the task-001 spike. The reusable recipe lives in `docs/headless-claude-cli-evals.md`. Load-bearing facts for `run.sh`:

- **Auth**: `cp ~/.claude/.credentials.json $CFG/` into a relocated `CLAUDE_CONFIG_DIR` is sufficient; fail fast if the source file is absent.
- **Two hard conditions**: (1) workspace cwd MUST be outside the repo tree (`mktemp -d`, never `.tmp/` — cwd walk-up re-discovers the repo's skills + CLAUDE.md); (2) do **not** pass `--setting-sources ''` (it silently kills the skill-under-test).
- **With-skill arm** = drop compiled skill at `$CFG/skills/assurance-strategist/` (SKILL.md + references/). **Baseline arm** = identical minus that directory. The arms differ by exactly one skill dir.
- **Invocation**: `CLAUDE_CONFIG_DIR=$CFG claude -p "<prompt>" --output-format json --strict-mcp-config --permission-mode bypassPermissions --model <pinned> < /dev/null`.
- **Output**: parse `.result` (final assistant message only — structured reports must be emitted last); keep whole JSON as evidence.
- **Floor**: ~14 built-in slash commands appear in both arms; harmless to the differential.

## Related Tasks

- **Task 001 spike** (`docs/assurance-eval-isolation-spike.md`) — verdict GO (conditional); validates the clean-room recipe above. Same task, exploratory phase already complete.
- **Research diary** (`docs/assurance-strategist-research-diary.md`) — settled decisions this task implements: card schema **v3.2** (12 architect-facing sections), flat card frontmatter, `{{ index:techniques }}` generated from frontmatter, `technique-<slug>.md` naming, evals are repo-internal dev infra (T1/T2 + grader-lite in scope; T3-full/T4 out), the skill is the **architect** (designs assurance for downstream agents, not a verifier).

## Git History & Current State (updated 2026-06-15)

- **`3fcf09e`** is current HEAD. Since planning docs were committed, the **`reflection`** module (`learning-diary` skill) was added (`cd1489a`) — the repo now has **6 modules** (planning, ideation, maintenance, exploration, rich-docs, reflection), not 5. The solution's `compile([...])` call and all plan references updated accordingly.
- **`8ea4266`** "Add task 001 assurance-eval groundwork; fix auto doc/skill tooling rename" added this task's docs (requirements + research diary + spike + headless-cli reference) and renamed tooling CLIs. **It added docs only — no `src/` code.** Confirmed `ls src/assurance` → *No such file or directory*. This task is the first to write `src/assurance/`.
- **`9d9279e`** added the planning-doc skill + pd-components, and earlier work "Generate install.sh during compilation" — so `src/compile.py` already generates `install.sh` from the module list; the new `assurance` module auto-registers there once declared.
- **`c1cc7df`** added the husky pre-commit hook → runs `scripts/pre-commit-checks.sh` (compile → lint → doc checks → skill sync). Its compile step is `python3 src/compile.py` (the line this task migrates to `uv run`).
- **Tooling rename**: the CLIs are now `auto skill …` / `auto doc …` (e.g. `auto skill lint`, `auto skill sync`, `auto doc stale`). `scripts/pre-commit-checks.sh` uses the new names; **`Makefile:21` still has the old `autoskill lint`** — a pre-existing inconsistency, **out of scope** for this task (don't "fix" it as a side effect).
- **No `pyproject.toml` / `uv.lock` / `.python-version`** exist yet (never committed) — this task introduces them.
- **`.gitignore`** exists (currently: `.tmp`, `skills-lock.json`, `.ntm`, `node_modules/`, `planning-doc-workspace/`); this task appends `src/assurance/evals/results/*` and `.venv/`.
- **Task 001 is the only task** in `docs/tasks/`; no prior task patterns to mirror beyond the module/compiler conventions above.
