# Context: Task 002

Codebase facts grounding the [solution](./solution.md) for the beta-planning-workflow: how the compiler processes templates and refs, how skills reference each other, and how pd-components structure HTML docs.

## Key Files

### The compiler — `src/compile.py`

- `src/compile.py:48-51` — the two existing directives:
  - `REF_PATTERN = re.compile(r"^\{\{\s*ref:(.+?)\s*\}\}$", re.MULTILINE)` — line-anchored, inline-expands a ref file.
  - `REF_LINK_PATTERN = re.compile(r"\[references/(.+?)\]\(references/", re.MULTILINE)` — detects markdown links to refs (for cross-checking).
  - `MAX_OUTPUT_CHARS = 15_000`.
- `src/compile.py:69-138` — Phase 1 validation. Checks: module dir exists, template exists, all declared refs exist, frontmatter has `name`+`description`, cross-checks `{{ ref:X }}` usage in templates against DSL declarations (lines 119-128: undeclared-but-used = ERROR, declared-but-unused = WARN).
- `src/compile.py:157-163` — Phase 2 rendering. `replace_ref` reads the ref file and `REF_PATTERN.sub(replace_ref, content)` inlines it. This is where a new `{{ skill:X }}` substitution pass would go (after ref expansion, before size check).
- `src/compile.py:180-187` — Ref copying. Uses `shutil.copy2` for verbatim binary copy — **refs are NOT expanded or rendered**. This must change for `{{ skill:X }}` to work inside reference files.
- `src/compile.py:305-348` — `__main__`: modules are hard-coded. Adding `src/beta-planning/` requires a new `module(...)` declaration appended here.

### Source template structure

- `src/planning-workflow/skills/new-task/SKILL.md:30` — hard-coded reference: `"run /new-solution to continue"`
- `src/planning-workflow/skills/new-solution/SKILL.md:46` — hard-coded reference: `"run /new-plan to continue"`
- `src/planning-workflow/skills/new-plan/SKILL.md:42` — hard-coded references: `"run /review-task for a review or /commit-task to finalize"`
- `src/planning-workflow/refs/workflow-overview.md:9-18` — hard-coded pipeline diagram with all skill names (`/new-task`, `/new-solution`, `/new-plan`, `/review-task`, `/commit-task`, `/execute-task`, etc.)

### pd-components boilerplate and attributes

- `pd-components/dist/llms.txt` — component reference. Pin to `pd-v0.3.0`. Key components:
  - `<pd-doc title status pr generated>` — shell. Status: draft|in-review|approved. PR: "pending" or URL.
  - `<pd-tab name>` — tabbed pages. Deep links: `#tab:Name`.
  - `<pd-section id title>` — anchorable section with comment button.
  - `<pd-ac id title phases tests>` — acceptance criteria with traceability chips.
  - `<pd-stepper>` / `<pd-phase n title files status>` — plan walkthrough.
  - `<pd-thread anchor status priority title>` / `<pd-comment by>` — append-only review threads.
  - `<pd-files>` / `<pd-file path change>` — file-change tree.
  - `<pd-mermaid caption>` — rendered diagrams (flowchart, sequence, state, class, ER, xychart only).
  - `<pd-decisions>` — auto-generated decision log from resolved threads.
  - `<md>` — client-side markdown rendering (token-efficient prose).

### Current task artifact conventions

- Task folder: `docs/tasks/$ID-$NAME/` (3-digit ID, kebab-case name)
- Branch: `task/$ID-$NAME`
- Current structure: `requirements.md`, `solution.md`, `context.md`, `plan.md` (4 files)
- Artifact sub-docs (wireframes, diagrams) stored alongside, linked from plan.md

## Patterns

- **Templates are process docs**: SKILL.md files are instructions the agent follows — they describe *what to do*, not the output format directly. Output format is in linked reference files (e.g. `template-requirements.md`).
- **Shared refs via DSL**: common reference files live in `refs/` and are declared per-skill in the DSL. The compiler copies them to each skill's `references/` directory.
- **Ref expansion is one-level**: `{{ ref:X }}` in SKILL.md expands the ref inline. Refs themselves are never expanded (copied verbatim). The `{{ skill:X }}` directive breaks this pattern by needing substitution in refs too.
- **Line-anchored vs inline directives**: `{{ ref:X }}` is line-anchored (`^...$`) because it replaces an entire line with file contents. `{{ skill:X }}` is inline because it appears mid-sentence (e.g. "run `/{{ skill:beta-new-solution }}`").
- **Module isolation**: each module is self-contained under `src/<name>/`. Skills within a module share refs; cross-module sharing doesn't exist today (each module copies what it needs).

## Related Tasks

- Task 001: assurance-skill-walking-skeleton — designed (but **not yet merged to main**) an extension of the compiler with `{{ index:techniques }}` directive and card-schema validation. The implementation lives in an unmerged worktree (`.claude/worktrees/task+001-...`), not in `src/compile.py` on main. The pattern (line-anchored directive, Phase 1 validation, Phase 2 rendering via `.sub()`) is a useful model to follow, but task 002 must not assume any of that code is present — on main, `src/compile.py` has only `REF_PATTERN` (line 48) and `REF_LINK_PATTERN` (line 50). Task 002's `{{ skill:X }}` is inline (not line-anchored) and needs to work in refs too (not just templates).

<!-- RESOLVED(P2): Task 001's compiler changes are NOT in the base this task builds on
REVIEW: I verified against the current tree: `grep -n INDEX_PATTERN src/compile.py` returns nothing, commit `0ef31ce` is not in `git log`, and no `index:techniques` directive or assurance module exists under src/. Task 001 lives only in an uncommitted worktree (.claude/worktrees/task+001-...). So describing INDEX_PATTERN as an "existing" precedent is misleading — when this task is implemented on main, src/compile.py has only REF_PATTERN (line 48) and REF_LINK_PATTERN (line 50). The pattern is still a fine model to follow, but state it as "from the unmerged task 001 worktree" rather than as current code, and don't assume any of that code is present. This directly affects plan.md Step A.3 (see comment there).
AUTHOR: Reworded to explicitly state task 001 is unmerged. Clarified that compile.py on main has only REF_PATTERN and REF_LINK_PATTERN. The pattern is a model, not existing code.
-->

