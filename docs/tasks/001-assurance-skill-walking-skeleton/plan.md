# Plan: Task 001

## Summary
Bootstrap a uv-managed python project, extend `src/compile.py` with a generated technique index + card-schema validation, add the `assurance-strategist` skill with one unit-testing card, and stand up a two-arm headless eval harness — proving the assurance-skill infrastructure end-to-end.

## Changes
| Symbol | File | Description |
|--------|------|-------------|
| + | `pyproject.toml` | uv project: requires-python, `pytest` in a dev dependency group |
| + | `uv.lock` | committed lockfile |
| ~ | `Makefile` | `compile` via `uv run`; add `test` + `eval-assurance` targets |
| ~ | `scripts/pre-commit-checks.sh` | compile step → `uv run python src/compile.py` |
| ~ | `.gitignore` | add `src/assurance/evals/results/*`, `.venv/` |
| ~ | `src/compile.py` | `INDEX_PATTERN`, `render_techniques_index`, `_validate_card`, required-keys/sections consts, used-refs fix, register `assurance` module |
| ~ | `src/CLAUDE.md` | document `{{ index:techniques }}` directive + `technique-*.md` card convention |
| + | `src/assurance/skills/assurance-strategist/SKILL.md` | minimal architect stub + `{{ index:techniques }}` |
| + | `src/assurance/refs/technique-unit-testing.md` | one complete schema-v3.2 card (flat frontmatter + 12 exact-title sections) |
| + | `src/assurance/tests/test_compiler.py` | pytest: AC-2 (index regen) + AC-3 (malformed card fails) |
| + | `src/assurance/evals/run.sh` | orchestrator: clean-room recipe, both arms, grader, report; runner + grader stub seam |
| + | `src/assurance/evals/cases/calculator-cli/prompt.md` | "build a calculator CLI that can add numbers" |
| + | `src/assurance/evals/cases/calculator-cli/checks.sh` | mechanical T1/T2 → scorecard (takes a workspace dir) |
| + | `src/assurance/evals/graders/strategy-rubric.md` | short rubric; pins JSON dimension keys |
| + | `src/assurance/evals/grade_report.py` | parse arm JSON + scorecards + grader JSON → report.md |
| + | `src/assurance/evals/README.md` | how to run + pointer to `docs/headless-claude-cli-evals.md` |
| + | `src/assurance/evals/results/.gitkeep` | run outputs land here (gitignored) |

## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)

## How to Test
- [ ] `uv run pytest src/assurance/tests/test_compiler.py` — AC-2 + AC-3 green
- [ ] `make compile` — all existing 5 modules + `assurance-strategist` compile; generated index row present; card copied to `references/`, linked not inlined (AC-1)
- [ ] `make eval-assurance AGENT_RUNNER=stub` — deterministic pipeline smoke: report.md with all three sections (no live calls)
- [ ] `make eval-assurance` — live two-arm run; report.md with real T1/T2 + grader scores (AC-4/5/5b evidence)

## Execution Sequence
```
Phase A (uv + build wiring)
   └─> Phase B (compiler: directive + validation)
          ├─> Phase C (assurance module content + register) ──> Phase E (eval harness)
          └─> Phase D (pytest compiler tests)
```
- B depends on A (uv runner). C and D both depend on B. E depends on C (needs the compiled skill) + A (make target). D is independent of C/E and can run in parallel.

## Plan

### Phase A: uv project + build wiring
- [ ] Step A.1: `uv init` (or hand-write) `pyproject.toml` — project name, `requires-python = ">=3.12"`, a `[dependency-groups] dev = ["pytest"]` (or `[tool.uv]` dev-dependencies). Keep runtime deps empty (compiler is stdlib-only).
- [ ] Step A.2: `uv lock` to generate `uv.lock`; `uv sync` to materialize the env. Verify: `uv run python -c "import sys; print(sys.version)"` runs; `uv run pytest --version` prints a version (pytest resolved).
- [ ] Step A.3: `Makefile` — change `compile:` recipe to `uv run python src/compile.py`; add `test:` → `uv run pytest src/assurance/tests/`; add `eval-assurance: compile` → `bash src/assurance/evals/run.sh`. Leave the `lint:` line (`autoskill lint`) untouched (out of scope). Verify: `make compile` compiles all existing modules with no regression (output lists the 5 existing modules' skills; exit 0).
- [ ] Step A.4: `scripts/pre-commit-checks.sh` — change the compile step `python3 src/compile.py` → `uv run python src/compile.py`. Verify: `bash scripts/pre-commit-checks.sh` reaches the compile step and it passes (other steps may need `auto` CLIs; confirm compile sub-step prints OK).
- [ ] Step A.5: `.gitignore` — append `src/assurance/evals/results/*`, `!src/assurance/evals/results/.gitkeep`, `.venv/`. Verify: `git check-ignore src/assurance/evals/results/foo.json` matches; `.venv/` ignored.
- [ ] Step A.6: Commit: `chore(001): phase A - uv project bootstrap + build wiring`

### Phase B: compiler extensions (directive + validation)
- [ ] Step B.1: `src/compile.py` — add near line 48: `INDEX_PATTERN = re.compile(r"^\{\{\s*index:techniques\s*\}\}$", re.MULTILINE)`, `CARD_PREFIX = "technique-"`, `REQUIRED_CARD_KEYS = [...]` (the 13 flat keys), `REQUIRED_CARD_SECTIONS = [...]` (the 12 exact titles, in order).
- [ ] Step B.2: Add `_validate_card(path) -> list[str]`: parse frontmatter (reuse `_parse_frontmatter`), error per missing required key; scan `## ` headings, error per missing required title and per out-of-order title. Each error string is prefixed by the caller's `tag` + card filename.
- [ ] Step B.3: Wire `_validate_card` into Phase 1 (`~line 100-103`): for each declared ref whose filename starts with `CARD_PREFIX`, append its errors to `errors`. Verify: existing 5 modules still compile (they declare no `technique-*` refs, so no behavior change).
- [ ] Step B.4: Add `render_techniques_index(sk, refs_dir) -> str`: select `sk.refs` with `CARD_PREFIX`, parse each card's frontmatter, render a markdown table (cols: Technique=`name`, What it catches=`summary`, Oracle=`oracle`, Archetypes=`archetypes`, Crit=`criticality-min`, Volatility=`volatility-fit`, link to `references/<file>`).
- [ ] Step B.5: In Phase 2 render (`~line 163`, after `REF_PATTERN.sub`, before the size check): `rendered = INDEX_PATTERN.sub(lambda m: render_techniques_index(sk, refs_dir), rendered)`.
- [ ] Step B.6: Phase-1 used-refs fix (`~line 120`): if `INDEX_PATTERN.search(template)`, add every declared `technique-*.md` filename to `used_refs` so it isn't flagged declared-but-unused.
- [ ] Step B.7: `src/CLAUDE.md` — under Templating, document the new `{{ index:techniques }}` directive and the `technique-<slug>.md` card convention (frontmatter keys + 12 exact-title sections, validated at compile time).
- [ ] Step B.8: Verify: `make compile` still green for all existing modules (no `assurance` module yet). `uv run python -c "import sys; sys.path.insert(0,'src'); import compile; print(hasattr(compile,'_validate_card'), hasattr(compile,'render_techniques_index'))"` → `True True`.
- [ ] Step B.9: Commit: `feat(001): phase B - {{ index:techniques }} directive + card-schema validation`

### Phase C: assurance module content + registration
- [ ] Step C.1: Write `src/assurance/skills/assurance-strategist/SKILL.md` — frontmatter (`name`, `description` per repo description rules); body: architect identity, self-verification invariant (100% autonomy; evidence is the only trust), the four axes named, the `{{ index:techniques }}` directive line, and "read the card before prescribing." No axes-intake/composition/maturity content.
- [ ] Step C.2: Write `src/assurance/refs/technique-unit-testing.md` — flat frontmatter with all 13 `REQUIRED_CARD_KEYS`; body with all 12 exact-title `## ` sections in order, concise but real unit-testing content (oracle=exact, archetypes incl. algorithmic-core/crud-surface, criticality-min=C1, etc.).
- [ ] Step C.3: `src/compile.py` `__main__` — add `assurance = module("assurance", skill("assurance-strategist", refs=[ref("technique-unit-testing.md")]))` and append `assurance` to the `compile([...])` list.
- [ ] Step C.4: `make compile`. Verify (AC-1): `skills/assurance-strategist/SKILL.md` exists; it contains a generated markdown table row for unit-testing with a `references/technique-unit-testing.md` link; the literal `{{ index:techniques }}` is gone; the card body is NOT inlined (grep SKILL.md for a unique card section title → absent); `skills/assurance-strategist/references/technique-unit-testing.md` exists. `install.sh` lists the `assurance` module.
- [ ] Step C.5: Verify size: compiled SKILL.md is well under 15k chars (printed by compiler).
- [ ] Step C.6: Commit: `feat(001): phase C - assurance-strategist skill + unit-testing card`

### Phase D: pytest compiler tests (parallel to C, after B)
- [ ] Step D.1: `src/assurance/tests/test_compiler.py` — helper that writes a throwaway module (skill SKILL.md with `{{ index:techniques }}` + one `technique-foo.md` card) into a `tmp_path` src tree and calls `compile.compile([...], src_dir=tmp, out_dir=tmp_out)` in-process.
- [ ] Step D.2: `test_index_regenerates` (AC-2): compile once, read the index row; rewrite the card's `summary:`; recompile; assert the index row changed and the SKILL.md source was never edited.
- [ ] Step D.3: `test_malformed_card_missing_key` + `test_malformed_card_missing_section` (AC-3): build a card missing a required frontmatter key / a required section; assert `compile.compile(...)` raises `SystemExit` with non-zero code and `capsys` stderr names the card filename + the missing element.
- [ ] Step D.4: `test_real_module_compiles` (AC-1 backstop, only meaningful after C): run `make compile` via subprocess or assert the committed `skills/assurance-strategist/SKILL.md` contains the generated row. (Skip/xfail-guard if C not yet merged.)
- [ ] Step D.5: Verify: `uv run pytest src/assurance/tests/ -v` → all pass. `make test` green.
- [ ] Step D.6: Commit: `test(001): phase D - compiler index-regen + card-validation tests`

### Phase E: eval harness
- [ ] Step E.1: `cases/calculator-cli/prompt.md` (the build prompt) + an empty starting workspace convention (no fixture dir needed; document it). `graders/strategy-rubric.md` — short rubric naming the JSON dimension keys (e.g. `tests_present`, `verify_command`, `evidence`) and a 0–3 scale.
- [ ] Step E.2: `checks.sh $WS` — T1: probe for harness files (a testing doc, a verify/test entry, a tests location) per a documented priority list; T2: probe `make verify` → `make test` → `npm test` → `pytest`, run the first present, record exit code. Emit a small JSON scorecard to stdout. Verify: against a hand-made fixture dir with a trivial test, `checks.sh` emits valid JSON and a correct T2 exit code.
- [ ] Step E.3: `run.sh` — implement the clean-room recipe (mktemp outside repo, copy creds, with-skill arm drops `skills/assurance-strategist/`, pinned `--model`, the documented flags, `< /dev/null`). Abstract the agent call into `run_agent_arm()` and the grader into `run_grader()`; both honor `AGENT_RUNNER=stub` (write canned `out.json` / grader JSON) for deterministic, tokenless verification. Fail fast if `~/.claude/.credentials.json` is absent in live mode.
- [ ] Step E.4: `grade_report.py` — read both arms' `out.json`, the T1/T2 scorecards, and the grader JSON; write `results/<run>/report.md`: header (case, model, skill version, timestamp), side-by-side mechanical scorecard table, grader-score table, blank `## Human verdict` section. Run via `uv run python`.
- [ ] Step E.5: `README.md` (how to run, stub vs live, pointer to `docs/headless-claude-cli-evals.md`); `results/.gitkeep`.
- [ ] Step E.6: Verify (stub, deterministic): `make eval-assurance AGENT_RUNNER=stub` → `results/<run>/report.md` exists and contains the mechanical table, the grader-score table, and a `## Human verdict` heading (AC-5b structure). Both arms differ by exactly the skill dir (assert with-skill `$CFG/skills/assurance-strategist` created, baseline not).
- [ ] Step E.7: Verify (live evidence): `make eval-assurance` with real creds → report.md populated with real `.result`-derived scorecards for both arms; keep the run dir as the evidence bundle (AC-4/AC-5).
- [ ] Step E.8: Commit: `feat(001): phase E - two-arm eval harness + report`

## Success Criteria
- [ ] **AC-1**: `make compile` produces `skills/assurance-strategist/SKILL.md` with a generated technique-index row and `references/technique-unit-testing.md` (linked, not inlined).
- [ ] **AC-2**: `test_index_regenerates` passes — editing card frontmatter + recompiling changes the index with no SKILL.md edit.
- [ ] **AC-3**: `test_malformed_card_*` pass — a card missing a required key or section fails the build (non-zero exit) with an error naming the card + element.
- [ ] **AC-4**: live `make eval-assurance` produces the with-skill arm's captured project + T1/T2 scorecard.
- [ ] **AC-5**: same run produces the baseline arm and a with-vs-without comparison report.
- [ ] **AC-5b**: report shows mechanical + grader scores side by side and a preserved `## Human verdict` section.
- [ ] **AC-6**: `make compile` and `make eval-assurance` each run as a single command.
- [ ] `make test` green; `make compile` green (no regression to existing 5 modules); stub eval run deterministic.

## Open Questions
- (none — Q1–Q4 resolved in requirements; the four solution-stage design choices confirmed 2026-06-13; uv adopted per user direction)
