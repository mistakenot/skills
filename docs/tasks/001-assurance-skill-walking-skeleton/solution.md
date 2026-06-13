# Solution: Task 001

Walking skeleton for the `assurance-strategist` skill bundle: one skill + one technique card compiled by an extended `src/compile.py`, plus a two-arm headless eval harness. Proves the infrastructure end-to-end before the ~30-card library is authored. See [context.md](./context.md) for the codebase facts this builds on.

## Approach

### A. The `src/assurance/` module (AC-1)

1. Create `src/assurance/skills/assurance-strategist/SKILL.md` — the **minimal stub** (per requirements Q2): identity ("you are the assurance architect"), the self-verification invariant (agents are 100% autonomous; evidence is the only trust mechanism), the four axes named, a `{{ index:techniques }}` directive where the routing table is generated, and the rule "read the card before prescribing." No axes intake / composition frames / maturity presets yet — those land in a follow-up task.
2. Create `src/assurance/refs/technique-unit-testing.md` — one **complete** technique card (per Q1: unit testing is the simplest to validate mechanically). Flat frontmatter (routing layer) + the 12 architect-facing body sections of schema v3.2. Content is real but concise; the task proves the schema/pipeline, not card depth.
3. Register the module in `src/compile.py:__main__`:
   ```python
   assurance = module("assurance",
       skill("assurance-strategist", refs=[ref("technique-unit-testing.md")]),
   )
   # ...
   compile([planning, ideation, maintenance, exploration, rich_docs, assurance])
   ```
   The card is **linked** by the generated index, not inlined — so Phase 2 copies it to `references/technique-unit-testing.md` and SKILL.md only holds the index row.

### B. Compiler extension: `{{ index:techniques }}` (AC-1, AC-2)

1. Add `INDEX_PATTERN = re.compile(r"^\{\{\s*index:techniques\s*\}\}$", re.MULTILINE)` and a `CARD_PREFIX = "technique-"` constant near `src/compile.py:48`.
2. In Phase 2 render (`src/compile.py:~163`, right after `REF_PATTERN.sub`, before the size check), substitute the directive with a generated markdown table. A `render_techniques_index(skill, refs_dir)` helper:
   - selects declared refs whose filename starts with `technique-`,
   - parses each card's flat frontmatter via the existing `_parse_frontmatter`,
   - emits one table row per card: **name · summary (what it catches) · oracle · archetypes · criticality-min · volatility-fit · link** to `references/<file>`.
   - Because the index is generated from frontmatter, editing a card's `summary:` and recompiling changes the row with zero SKILL.md edits (AC-2).
3. Phase 1 cross-check fix (`src/compile.py:119-128`): when a template contains the index directive, treat all declared `technique-*.md` refs as "used" so they don't trip the declared-but-unused warning.

### C. Compiler extension: card-schema validation (AC-3)

In Phase 1 (`src/compile.py:~109`, the natural validation home), for every declared ref whose filename starts with `technique-`, run `_validate_card(path) -> list[str]`:
- **Frontmatter**: required flat keys all present — `name`, `summary`, `oracle`, `archetypes`, `criticality-min`, `volatility-fit`, `harness`, `pairs-with`, `upgrade-looser`, `upgrade-stricter`, `cost-author`, `cost-maintain`, `cost-run`. Missing key → error naming the card + key. **Value formats (pinned, since the flat parser stores raw strings):**
  - `oracle` ∈ {`exact`, `relational`, `reference`, `spec`, `judgment`}; `volatility-fit` ∈ {`loose`, `strict`, `both`}; `harness` ∈ {`ad-hoc`, `playbook`, `ci`} (the harness-durability tier the technique targets — from the diary's routing-layer frontmatter); `criticality-min` ∈ {`C1`..`C4`}; `cost-*` ∈ {`low`,`medium`,`high`} (run: `fast`/`medium`/`slow`).
  - **List-valued keys are bare comma-separated strings, NOT YAML lists** — `archetypes: algorithmic-core, crud-surface` and `pairs-with: differential-testing, mutation-testing` (no `[...]` brackets, which the flat parser would keep literally and leak into the index row). `_validate_card` only checks presence in this task; value-enum linting is a documented later enhancement (note it, don't build it here — the one authored card simply conforms).
- The `harness`, `pairs-with`, `upgrade-*`, and `cost-*` keys are required so every card carries the full routing schema even though the v1 index renders only a subset of columns — this keeps cards forward-compatible with richer routing/filters without a re-migration.

<!-- RESOLVED(P3): the `harness` frontmatter key has no defined meaning or value
REVIEW: `harness` is required by REQUIRED_CARD_KEYS and will fail the build if absent, but it isn't in the diary's routing-layer frontmatter example (lines 330-337), it isn't rendered in the index columns (§B lists name/summary/oracle/archetypes/criticality-min/volatility-fit/link), and nothing here defines what value it holds. The Phase C.2 card author has to invent it with no guidance. Either define the key's semantics/allowed values (one line), drop it from the required set for the skeleton, or note it's a placeholder. Same question applies to whether `archetypes` should be a comma-string (flat parser keeps `[a, b]` brackets literally) — pin the value format so the generated index row reads cleanly.
AUTHOR: Pinned value formats for every key: `harness` ∈ {ad-hoc, playbook, ci} (harness-durability tier, per the diary routing-layer frontmatter), plus enums for oracle/volatility-fit/criticality-min/cost-*. Defined list-valued keys (`archetypes`, `pairs-with`) as bare comma-separated strings — no `[...]` brackets — so the flat parser doesn't leak brackets into the index row. Kept the full key set required (cards stay forward-compatible with richer routing); noted that value-enum linting is a later enhancement, not built in this task.
-->

- **Body sections** (**exact-title H2 matching** — chosen at assumption check): the 12 schema-v3.2 section titles must each appear as an `## <exact title>` heading, in order. The validator holds the canonical `REQUIRED_CARD_SECTIONS` list (the source of truth for card titles); it scans the card's `## ` headings, requires every required title present, and requires their relative order to match the canonical sequence. A missing or reordered title → error naming the card + the offending title. (Trade-off accepted: a heading-wording change requires a one-line update to `REQUIRED_CARD_SECTIONS` — the titles are deliberately pinned as the schema contract.)
- Errors append to the existing Phase-1 `errors` list, so a malformed card fails the build with a tagged message before anything is written.

The 12 canonical titles (schema v3.2, architect-facing): `What it is & what it catches/misses`, `When to prescribe / when not`, `Prerequisites`, `Design decisions`, `Derivation guidance`, `Minimum viable instance vs full rigor`, `Harness changes`, `How to get to a walking skeleton`, `Acceptance criteria to embed`, `Composition`, `Failure modes & retirement triggers`, `Tool pointers`.

### D. Eval harness skeleton — `src/assurance/evals/` (AC-4, AC-5, AC-5b)

`run.sh` is the orchestrator and implements the de-risked clean-room recipe. Flow:

1. **Preflight**: assert `~/.claude/.credentials.json` exists (fail fast); pin `--model` via a `MODEL` env var with a sensible default.
2. **For each arm** (`baseline`, `withskill`):
   - `BASE=$(mktemp -d)` outside the repo; `CFG=$BASE/config`, `WS=$BASE/ws`; `cp` credentials into `CFG`.
   - `withskill` only: copy the compiled `skills/assurance-strategist/` into `$CFG/skills/assurance-strategist/`.
   - copy the case's starting workspace (empty for calculator-cli) into `WS`.
   - invoke the agent via a `run_agent_arm()` shell function (the **runner seam** — currently `claude -p` per Q4; a `run_agent_arm_codex()` can be swapped in later without touching orchestration). Capture `out.json`.
3. **Mechanical checks** (`cases/calculator-cli/checks.sh $WS` per arm) → a small scorecard:
   - **T1**: expected harness files exist (a testing doc, a verify/test entry point, a tests location) — probed against a documented priority list.
   - **T2**: the project's test command runs and its exit code is recorded — `checks.sh` probes `make verify` → `make test` → `npm test` → `pytest` and runs the first present. **No-command-found branch (explicit):** if none of the probes match, the scorecard emits a distinct, valid state — `{"t2_command": "none", "t2_status": "absent", "t2_exit": null}` — rather than crashing or emitting an empty exit code. When a command IS found: `{"t2_command": "<cmd>", "t2_status": "ran", "t2_exit": <int>}` (any exit code, including non-zero, is a valid recorded outcome — see AC-4). This is the expected baseline-arm signal (a test-less project), and `grade_report.py` treats `"absent"` as a first-class comparable value, never an error. `checks.sh` always emits well-formed JSON and exits 0 itself (it reports on the project; it doesn't adopt the project's exit code as its own).

<!-- RESOLVED(P2): checks.sh must define the "no recognised test command" outcome explicitly
REVIEW: The whole point of the differential is that the baseline arm (no skill) will often produce a project with NO recognised test command — that is the signal the skill should improve. But T2 only describes "run the first present". What does the scorecard emit when none of make verify / make test / npm test / pytest is present? It must be a distinct, valid scorecard state (e.g. command="none", status="absent"), not a crash, an empty exit code, or invalid JSON that breaks grade_report.py downstream. Please specify the no-command-found branch so a test-less baseline produces a clean comparable scorecard rather than an error.
AUTHOR: Specified the no-command branch: `{"t2_command":"none","t2_status":"absent","t2_exit":null}` (distinct, valid JSON), vs `{"t2_command":"<cmd>","t2_status":"ran","t2_exit":<int>}` when found. checks.sh always emits well-formed JSON and exits 0 itself; grade_report.py treats "absent" as a first-class comparable value. Plan E.2 updated to test the no-command fixture path.
-->

4. **Grader-lite** (AC-5b — **JSON-scoring grader** chosen at assumption check): a third clean-room `claude -p` call (no skill) reads `graders/strategy-rubric.md` + a digest of both arms (file list + T1/T2 scorecard + each arm's `.result`) and emits, as its **final message**, structured JSON — a score per rubric dimension for each arm (e.g. `{"baseline": {...}, "withskill": {...}}`). The grader prompt pins the dimension keys and score range so the output is parseable. The raw JSON is kept as a run artifact.
5. **Report assembly** (`grade_report.py` — **python helper** chosen at assumption check): `run.sh` shells out to `uv run python src/assurance/evals/grade_report.py`, which reads both arms' `out.json`, the T1/T2 scorecards, and the grader JSON, then writes `results/<run>/report.md`: header (case, model, skill version, timestamp), a mechanical scorecard table (baseline vs withskill, side by side), a grader-score table rendered from the parsed JSON, and a blank `## Human verdict` section. **Durability split (option b):** `report.md` is the durable evidence carrier and is **git-tracked** — the human verdict written into it is committed and survives a fresh clone/CI; the bulky run artifacts copied into the same run dir as evidence (each arm's `out.json` transcript, the raw grader JSON, the T1/T2 scorecards) are gitignored. So `.gitignore` ignores everything under `results/` **except** `**/report.md` (and `.gitkeep`). (The clean-room `config/` with copied credentials lives in the `mktemp -d` dir **outside** the repo and is never placed under `results/`, so it can't be committed regardless.) This satisfies AC-5b's "preserved with the run results": the verdict lives in `report.md` next to its run, and is committable. `run.sh` stays the orchestrator (clean-room + process control); the python helper owns JSON parsing + report rendering.

<!-- RESOLVED(P2): "Human verdict preserved" conflicts with results/ being gitignored
REVIEW: AC-5b requires the human verdict/notes to be "preserved with the run results". But §E and the Files block gitignore `src/assurance/evals/results/*` (keep only `.gitkeep`), so the report.md a human edits — and the verdict in it — is local-only and never committed; it's lost on a fresh clone / CI / another machine. "Preserved" here means only "lives in the same run dir on this disk". If a verdict is meant to be durable evidence (the human-feedback loop of AC-5b), gitignoring it defeats that. Either (a) state explicitly that verdicts are intentionally ephemeral/local for the skeleton, or (b) give the verdict a committed home (e.g. a small curated results file outside results/, or un-ignore report.md per run).
AUTHOR: Took option (b): `report.md` (the verdict carrier) is git-tracked, so verdicts are durable/committable; the bulky run artifacts copied into the run dir as evidence (each arm's out.json transcript, raw grader JSON, scorecards) stay gitignored. `.gitignore` becomes the standard "ignore all but" pattern — ignore everything under results/ except `**/report.md` and `.gitkeep`. (Credentials never enter results/ — they live in the out-of-repo mktemp config dir.) Updated §E, the Files block, and plan A.5.
-->

> **Grader-JSON parsing (defensive):** `grade_report.py` must not do a bare `json.loads(.result)` — the grader is an LLM and may wrap JSON in ```json fences or prepend a sentence. It strips code fences and extracts the first balanced `{...}` block before parsing, and on failure **degrades gracefully**: the report renders a `grader: parse failed` row and embeds the raw `.result` verbatim, rather than crashing the whole report. (The `AGENT_RUNNER=stub` grader returns clean JSON, so the deterministic path is unaffected.)

<!-- RESOLVED(P3): grader final-message JSON parsing should be defensive against markdown fences
REVIEW: The grader is a `claude -p` call told to emit JSON as its final message, parsed from `.result`. LLMs frequently wrap JSON in ```json fences or add a leading sentence even when told not to. If grade_report.py does a bare json.loads(.result) it will intermittently fail and break the report. Recommend grade_report.py strip code fences / extract the first {...} block before parsing, and degrade gracefully (record "grader parse failed", keep raw .result) rather than crashing the whole report.
AUTHOR: Added a defensive-parsing spec to grade_report.py: strip code fences, extract the first balanced {...} block, and on failure render a "grader: parse failed" row with the raw .result embedded rather than crashing. Plan E.4 updated to require this + a unit check on a fenced sample.
-->


### E. Makefile + gitignore wiring (AC-6)

- `make eval-assurance` → `bash src/assurance/evals/run.sh` (one-line wrapper, matching existing target style). Depends on `compile` so the with-skill arm uses fresh output.
- `make compile` already satisfies the build half of AC-6.
- `.gitignore`: ignore run artifacts under `src/assurance/evals/results/` **except** committed evidence — standard "ignore all but" pattern keeping `**/report.md` (the verdict carrier) and `.gitkeep` tracked, plus `.venv/`.

## Files

```
+ src/assurance/skills/assurance-strategist/SKILL.md      # minimal architect stub + {{ index:techniques }}
+ src/assurance/refs/technique-unit-testing.md            # one complete schema-v3.2 card (flat frontmatter + 12 sections)
+ src/assurance/evals/run.sh                              # orchestrator: clean-room recipe, both arms, grader, report
+ src/assurance/evals/cases/calculator-cli/prompt.md      # "build a calculator CLI that can add numbers"
+ src/assurance/evals/cases/calculator-cli/checks.sh      # mechanical T1/T2 → scorecard (takes a workspace dir)
+ src/assurance/evals/graders/strategy-rubric.md          # short grader-lite rubric (dimensions pinned for JSON output)
+ src/assurance/evals/grade_report.py                     # parse arm JSON + scorecards + grader JSON → report.md
+ src/assurance/evals/results/.gitkeep                    # run dir; artifacts gitignored, except per-run report.md (tracked)
+ src/assurance/evals/README.md                           # how to run + pointer to headless-claude-cli-evals.md
+ src/assurance/tests/test_compiler.py                    # pytest: AC-2 (index regen) + AC-3 (malformed card fails)
~ src/compile.py                                          # INDEX_PATTERN + render_techniques_index + _validate_card + register module
~ src/CLAUDE.md                                           # document the {{ index:techniques }} directive + card convention
~ Makefile                                                # compile via `uv run --no-dev`; test via `uv run pytest`; eval target
~ .gitignore                                              # ignore evals/results/* except **/report.md + .gitkeep; + .venv/
+ pyproject.toml                                          # new: uv project — requires-python, pytest in a dev dependency group
+ uv.lock                                                 # new: committed uv lockfile
~ scripts/pre-commit-checks.sh                            # compile step → `uv run --no-dev python src/compile.py`
```

> **Note (uv adoption):** the repo is currently stdlib-only python (no `pyproject.toml`/lockfile) and pytest is **not installed**. Per the decision to use **uv** for the project's python, this task introduces `pyproject.toml` + `uv.lock` (uv 0.10.9 is available), declares `pytest` in a dev dependency group, and routes every python invocation through `uv run`:
> - `make test` → `uv run pytest src/assurance/tests/`
> - `make compile` → `uv run --no-dev python src/compile.py` (was `python3 src/compile.py`) — **`--no-dev`** so the stdlib-only build never syncs/needs the dev group (pytest) on the commit path
> - `grade_report.py` → invoked from `run.sh` as `uv run --no-dev python src/assurance/evals/grade_report.py` (also stdlib-only)
> - `make test` → `uv run pytest src/assurance/tests/` (the **only** invocation that uses the dev group)
>
> Because `scripts/pre-commit-checks.sh` (the husky hook) also runs `python3 src/compile.py`, its compile step migrates to `uv run` too — so **uv becomes a requirement on the commit path** (and any CI). `compile.py`/`grade_report.py` stay stdlib-only, so uv here is the single runner + env manager, not a code dependency. **`make test` stays a separate target — it is NOT wired into `make check`** (see the P2 thread below): `check: compile lint` is left as-is so ordinary commits don't run the test suite and don't pull the stale `autoskill lint` into a new coupling.

<!-- RESOLVED(P2): "make check gains the test run" is asserted here but no plan step implements it
REVIEW: This sentence says `make check` will gain the test run, but plan.md Phase A.3 only changes the `compile:` recipe and ADDS `test:` + `eval-assurance:` targets — it explicitly says "Leave the lint line untouched" and never edits the `check:` target. Verified Makefile:25 is `check: compile lint` (no test). Either drop this claim or add a concrete A.3 sub-step to make `check: compile lint test` (note: `make check` would then also run `make lint`, which is the stale `autoskill lint` per context.md:55 — so wiring test into check pulls a known-broken target onto the path; worth deciding deliberately).
AUTHOR: Dropped the claim. `make check` stays `check: compile lint` (unchanged); `make test` is a standalone target run explicitly / in CI, not folded into check. Rationale: wiring test into check would also drag the known-stale `autoskill lint` onto a new path, and would run the suite on every `make check` — neither wanted for the skeleton. Solution note + plan A.3 now agree (test is added, check untouched).
-->

<!-- RESOLVED(P2): `uv run python src/compile.py` in the pre-commit hook will sync the dev group (pytest) on every commit
REVIEW: By default `uv run` ensures the project env — including the `dev` dependency group — is synced before running. compile.py is stdlib-only and needs nothing from that group, but routing the hook's compile step through plain `uv run` couples EVERY commit (husky hook + CI) to pytest being resolvable/cached; first run on a clean machine or offline could fail or stall the commit. Recommend the hook's (and Makefile compile's) compile step use `uv run --no-dev python src/compile.py` so the stdlib-only build doesn't drag the test toolchain onto the commit path; reserve the dev group for `make test`.
AUTHOR: Adopted `uv run --no-dev` for both the Makefile `compile` recipe and the pre-commit hook's compile step (and for grade_report.py — also stdlib-only). The dev group (pytest) is now pulled by exactly one invocation, `make test`. The commit path no longer depends on pytest being resolvable/cached. Updated the uv note above and plan steps A.3/A.4.
-->


Outline of the `src/compile.py` additions:

```python
INDEX_PATTERN = re.compile(r"^\{\{\s*index:techniques\s*\}\}$", re.MULTILINE)
CARD_PREFIX = "technique-"
REQUIRED_CARD_KEYS = ["name", "summary", "oracle", "archetypes", "criticality-min",
                      "volatility-fit", "harness", "pairs-with", "upgrade-looser",
                      "upgrade-stricter", "cost-author", "cost-maintain", "cost-run"]

def _validate_card(path: str) -> list[str]:
    """Return a list of error strings for a malformed technique card (frontmatter keys + ## 1..12 sections, ordered)."""

def render_techniques_index(sk: Skill, refs_dir: str) -> str:
    """Markdown table generated from each technique-*.md card's frontmatter."""
```

## Test Coverage

| AC | Test Type | File / Mechanism |
|----|-----------|------------------|
| AC-1 | compile smoke | `make compile` produces `skills/assurance-strategist/SKILL.md` (with a generated index row) + `references/technique-unit-testing.md`; asserted in `src/assurance/tests/test_compiler.py` |
| AC-2 | pytest (compiler) | `test_compiler.py`: edit a temp card's `summary`, recompile, assert the index row changed with no SKILL.md edit |
| AC-3 | pytest (compiler) | `test_compiler.py`: temp card missing a frontmatter key / an exact-title section → compile exits non-zero with an error naming the card + element |
| AC-4 | executable (eval) | `make eval-assurance` runs the with-skill arm; T1/T2 scorecard produced; demonstrated + transcript kept as evidence |
| AC-5 | executable (eval) | same run produces the baseline arm and the side-by-side comparison report |
| AC-5b | executable (eval) | report contains mechanical + grader-score sections and a preserved `## Human verdict` slot |
| AC-6 | smoke | `make compile` and `make eval-assurance` both run as single commands |

`test_compiler.py` runs under **pytest via uv** (`uv run pytest` — see the uv note above), using `tmp_path` fixtures to build a throwaway module and invoke the compiler (importing `compile.py`'s functions for AC-2, and a subprocess run for AC-3's non-zero exit). The eval ACs are proven by *running* the harness — fitting, since the skill's own doctrine is "grade by running, not reading."

## Out of Scope

- The full ~30-card catalog — only the one unit-testing card.
- Full SKILL.md (axes intake, composition frames, maturity presets) — minimal stub only.
- T3-full grader (multi-dimension rubric, per-case `expectations.yaml`) and T4 downstream-implementer simulation.
- CI integration for evals; N=3 variance runs (single run per arm).
- Real publishing/installing of the skill; planning-doc rich-doc output.
- A `codex` runner — only the `run_agent_arm()` seam is provided, not a second implementation.
- Pre-existing uncommitted repo changes (pd-components etc.).

## Rejected Alternatives

- **Numbered `## N.` headings for section validation** (considered, not chosen): would validate presence + order in one check, but the user chose exact-title matching so the section titles are the explicit, self-documenting schema contract; wording is pinned in `REQUIRED_CARD_SECTIONS`.
- **Bash-only eval orchestrator** (considered, not chosen): fewer moving parts, but JSON-score parsing + report assembly is clumsy in bash; a python `grade_report.py` owns that cleanly.
- **Grader emitting markdown directly** (considered, not chosen): simplest, but JSON scores are machine-readable for later aggregation across cases/runs.
- **Dependency-free / shell-only AC tests** (considered, not chosen): keeps the repo dependency-free, but pytest gives proper fixtures and assertions for the compiler tests; accepted cost is adopting uv + the first python dev dependency.
- **`pip` + `requirements-dev.txt` for pytest** (considered, not chosen): the user chose uv as the project's python tooling, so a `pyproject.toml` + `uv.lock` managed by `uv run` replaces an ad-hoc pip/venv flow.
- **Fully python eval orchestrator (`eval.py`) instead of `run.sh`**: requirements name `evals/run.sh`; bash keeps clean-room/process control, python handles only parsing + report.
- **Detecting cards by a frontmatter marker key instead of the `technique-` filename prefix**: the diary already fixes the `technique-<slug>.md` naming convention; keying index + validation off the same prefix is one rule, not two.
- **Globbing `refs/technique-*.md` for the index**: violates the repo's declare-everything DSL philosophy; cards stay explicitly declared, the directive just renders the declared set.
- **Inlining the card into SKILL.md via `{{ ref: }}`**: AC-1 requires linked-not-inlined; inlining also blows the 15k budget as the catalog grows.

## Appendix: Confirmed Design Decisions

Recorded from the step-9 assumption check (2026-06-13):

1. **Card section validation** → **Exact-title H2 matching.** The 12 schema-v3.2 titles are the pinned schema contract; `_validate_card` checks each exact `## <title>` present and in order. Heading-wording changes require updating the canonical `REQUIRED_CARD_SECTIONS` list.
2. **Eval orchestrator** → **Bash + small python helper.** `run.sh` orchestrates the clean room and arms; `grade_report.py` parses arm JSON + scorecards + grader JSON and writes `report.md`.
3. **Grader-lite** → **`claude -p` emitting scored JSON.** Per-dimension scores per arm; the harness parses and renders the comparison table.
4. **Compiler AC tests** → **Add pytest, managed by uv** (refined 2026-06-13 per "use uv for python scripts / project"). The repo becomes a uv project (`pyproject.toml` + `uv.lock`); pytest lives in a dev dependency group; `make test` runs `uv run pytest src/assurance/tests/`. All python invocations (compile, tests, grade_report) route through `uv run`, so uv joins the commit-path/CI requirements; the existing `scripts/pre-commit-checks.sh` compile step migrates accordingly.
