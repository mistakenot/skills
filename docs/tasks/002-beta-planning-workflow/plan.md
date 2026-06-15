# Plan: Task 002

## Summary
Extend `src/compile.py` with a `{{ skill:X }}` inline directive (validation + substitution in both templates and refs), create the `src/beta-planning/` module with three skills and their reference files, and update the planning-doc skill to preserve pd-meta blocks.

## Changes
| Symbol | File | Description |
|--------|------|-------------|
| ~ | `src/compile.py` | Add SKILL_REF_PATTERN, Phase 1 validation (resolve + ambiguity check), Phase 2 substitution, conditional ref rewriting |
| ~ | `src/CLAUDE.md` | Document `{{ skill:X }}` directive syntax and resolution rules |
| + | `src/beta-planning/refs/beta-workflow-overview.md` | Pipeline diagram using `{{ skill:X }}` references |
| + | `src/beta-planning/refs/html-boilerplate.md` | Starting HTML structure with pd-meta, pd-doc shell, script tags |
| + | `src/beta-planning/refs/tab-requirements.md` | Content guidelines: Problem, Goals, Out of Scope, Open Questions (no ACs) |
| + | `src/beta-planning/refs/tab-verification.md` | Content guidelines: test strategy, pd-ac cards, coverage map, gaps |
| + | `src/beta-planning/refs/tab-solution.md` | Content guidelines: approach, pd-files, rejected alternatives, pd-decisions |
| + | `src/beta-planning/refs/tab-plan.md` | Content guidelines: summary, execution DAG, pd-stepper/pd-phase, success criteria |
| + | `src/beta-planning/refs/template-context.md` | Context.md template (same rules as current planning-workflow version) |
| + | `src/beta-planning/skills/beta-new-task/SKILL.md` | Skill template: create plan.html with Requirements tab |
| + | `src/beta-planning/skills/beta-new-solution/SKILL.md` | Skill template: context.md + Verification tab + Solution tab |
| + | `src/beta-planning/skills/beta-new-plan/SKILL.md` | Skill template: Plan tab + AC traceability backfill |
| ~ | `src/rich-docs/skills/planning-doc/SKILL.md` | Add pd-meta preservation rule to authoring rules |

## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)

## How to Test
- [ ] `make compile` — all existing modules + beta-planning compile without errors
- [ ] Rename a skill in DSL, recompile — `{{ skill:X }}` outputs update (AC-2)
- [ ] Use invalid `{{ skill:nonexistent }}` — compiler errors with clear message (AC-3)
- [ ] Use ambiguous bare name across modules — compiler errors requiring qualified form
- [ ] `autoskill lint` — new skills pass linting
- [ ] Manual: invoke `/beta-new-task`, verify plan.html structure (AC-4)
- [ ] Manual: invoke `/beta-new-solution`, verify staged output + gates (AC-5)
- [ ] Manual: invoke `/beta-new-plan`, verify Plan tab + AC backfill (AC-6)

## Execution Sequence
```
Phase A (compiler: {{ skill:X }})
   └─> Phase B (beta-planning module: refs)
          └─> Phase C (beta-planning module: skills)
                 └─> Phase D (planning-doc update + final validation)
```
All phases are sequential — each depends on the previous.

## Plan

### Phase A: Compiler extension — `{{ skill:X }}` directive

- [x] Step A.1: Add `SKILL_REF_PATTERN = re.compile(r"\{\{\s*skill:(.+?)\s*\}\}")` near existing patterns in `src/compile.py`.
  - Verify: pattern compiles, matches `{{ skill:beta-new-solution }}` and `{{ skill:rich-docs/planning-doc }}` in a quick test.

- [x] Step A.2: In Phase 1 validation, after existing cross-checks (~line 128), build a global skill lookup dict mapping `skill_name -> module_name` for all modules. For each module/skill template, extract all `SKILL_REF_PATTERN` matches from template content. For each match:
  - If contains `/`: split into `module_name/skill_name`, verify both exist. Error if not.
  - If bare name: check global lookup. If name exists in exactly one module, resolve. If name exists in multiple modules (including the current one), **error and require the qualified form** — no implicit same-module preference. If zero modules, ERROR skill not found.

<!-- RESOLVED(P3): Bare-name resolution rule contradicts solution.md §A.2
REVIEW: solution.md §A.2 says a bare name should "resolve within same module first. If the name exists in multiple modules, error and require the qualified form" — i.e. prefer the same-module match. This step says "If multiple modules, ERROR" with no same-module preference. These disagree when a bare name exists both in the current module and another. It won't bite the beta-* names (all unique today), but pick one rule and make both docs match so the implementer isn't guessing. (Same-module-wins is the more ergonomic choice for intra-module refs.)
AUTHOR: Aligned both docs on "error on ambiguity, no implicit preference." This matches the user's earlier decision to error on ambiguity (recommended option). Updated solution.md §A.2 to remove the "resolve within same module first" phrasing that implied preference.
-->

  - Also scan each ref file in the module's `refs/` for `SKILL_REF_PATTERN` matches and apply the same validation.
  - Verify: add a temporary `{{ skill:new-task }}` to a test template, run compiler — should resolve without error. Add `{{ skill:nonexistent }}` — should fail.

<!-- RESOLVED(P2): Step anchors to `INDEX_PATTERN.sub(...)` which does not exist in base
REVIEW: Verified src/compile.py has no INDEX_PATTERN (that line lives only in the unmerged task-001 worktree; see context.md comment). On main, the only call here is `rendered = REF_PATTERN.sub(replace_ref, content)` at src/compile.py:163. Drop the "and the existing INDEX_PATTERN.sub(...)" phrasing — add the skill-ref pass immediately after the REF_PATTERN.sub line. Otherwise the implementer will search for a non-existent anchor.
AUTHOR: Removed the INDEX_PATTERN.sub reference. Step now correctly anchors to `REF_PATTERN.sub(replace_ref, content)` at src/compile.py:163 as the only existing substitution on main.
-->

- [x] Step A.3: In Phase 2 rendering, after `REF_PATTERN.sub(replace_ref, content)` (src/compile.py:163), add:
  ```python
  def replace_skill_ref(m: re.Match) -> str:
      raw = m.group(1).strip()
      if "/" in raw:
          _, skill_name = raw.split("/", 1)
      else:
          skill_name = raw
      return skill_name
  rendered = SKILL_REF_PATTERN.sub(replace_skill_ref, rendered)
  ```
  - Verify: compile existing modules — no change (no templates use `{{ skill:X }}` yet). No regressions.

- [x] Step A.4: Change the ref copying step. Replace the `shutil.copy2` loop with:
  ```python
  for r in sk.refs:
      src_path = os.path.join(refs_dir, r.filename)
      dst_path = os.path.join(refs_out, r.filename)
      with open(src_path) as f:
          ref_content = f.read()
      if SKILL_REF_PATTERN.search(ref_content):
          rendered_ref = SKILL_REF_PATTERN.sub(replace_skill_ref, ref_content)
          with open(dst_path, "w") as f:
              f.write(rendered_ref)
      else:
          shutil.copy2(src_path, dst_path)
  ```
  - Verify: `make compile` — all existing modules compile identically (no refs currently contain `{{ skill:X }}`). Diff compiled output before/after — no changes.

- [x] Step A.5: Update `src/CLAUDE.md` — add a section documenting the `{{ skill:X }}` directive:
  - Syntax: `{{ skill:<name> }}` (inline, not line-anchored)
  - Resolution: bare name resolves within module, errors on cross-module ambiguity; qualified `module/name` for explicit cross-module refs
  - Works in both SKILL.md templates and ref files
  - Verify: documentation reads clearly, no contradictions with existing content.

- [x] Step A.6: Commit: `feat(002): phase A — {{ skill:X }} compiler directive`
  - Verify: `make compile` passes, `autoskill lint` passes on existing skills.

### Phase B: Beta-planning module — reference files

- [ ] Step B.1: Create directory structure:
  ```
  mkdir -p src/beta-planning/refs
  mkdir -p src/beta-planning/skills/beta-new-task
  mkdir -p src/beta-planning/skills/beta-new-solution
  mkdir -p src/beta-planning/skills/beta-new-plan
  ```
  - Verify: directories exist.

- [ ] Step B.2: Write `src/beta-planning/refs/beta-workflow-overview.md` — pipeline diagram using `{{ skill:X }}` directives:
  ```
  ## Beta Workflow Overview

  Plan (on main)                 Execute                    Review & Complete
  ──────────────                 ───────                    ─────────────────
  /{{ skill:beta-new-task }}     /execute-task $ID          /address-feedback
    → plan.html (Req tab)         → worktree + branch      /complete-task
  /{{ skill:beta-new-solution }}   → subagent per phase      → merge
    → context.md                   → PR
    → plan.html (Verif + Sol)
  /{{ skill:beta-new-plan }}
    → plan.html (Plan tab)
  /review-task (optional)
  /commit-task
  ```
  Include conventions section (task folder structure, branch naming, pd-meta status lifecycle).
  - Verify: all `{{ skill:X }}` refs use names that will exist in the module DSL.

- [ ] Step B.3: Write `src/beta-planning/refs/html-boilerplate.md` — the starting HTML template agents use to create plan.html. Include:
  - Full HTML5 doctype + head with charset, viewport, title placeholder
  - `<script type="application/json" id="pd-meta">` with schema (all fields, nulls for unknowns)
  - Tailwind CDN script tag
  - pd-components script tag pinned to `pd-v0.3.0`
  - `<pd-doc>` shell with `status="draft"` and `pr="pending"`
  - A placeholder comment showing where tabs go
  - Verify: valid HTML when opened in browser (no rendering errors in console).

- [ ] Step B.4: Write `src/beta-planning/refs/tab-requirements.md` — content guidelines for the Requirements tab:
  - Sections: Problem (`<pd-section id="problem">`), Goals (`<pd-section id="goals">`), Out of Scope (`<pd-section id="out-of-scope">`), Open Questions (`<pd-section id="open-questions">`)
  - All content in `<md>` blocks
  - No acceptance criteria (those go in Verification tab)
  - Rules: stable ids, markdown prose, keep it concise
  - Verify: guidelines are clear and consistent with solution.md §C.

- [ ] Step B.5: Write `src/beta-planning/refs/tab-verification.md` — content guidelines for the Verification tab:
  - Sections: Test Strategy (`<pd-section id="test-strategy">`), optional `<pd-mermaid>` for coverage map, Acceptance Criteria (using `<pd-ac>` cards with empty `phases`/`tests` attributes), Known Gaps & Risks (`<pd-section id="verification-gaps">`)
  - Instruction: agent may scan and use any available project skills for testing/verification/assurance strategies
  - Rules: pd-ac `id` format is `AC-N`, Given/When/Then in `<md>` body, leave traceability attributes empty for Plan stage to fill
  - Verify: guidelines are clear and consistent with solution.md §D stage 2.

- [ ] Step B.6: Write `src/beta-planning/refs/tab-solution.md` — content guidelines for the Solution tab:
  - Sections: Approach (`<pd-section id="approach">`), File Changes (`<pd-files>` with `<pd-file>` entries), Rejected Alternatives (`<pd-section id="rejected-alternatives">`), Decision Log (`<pd-decisions>`)
  - Rules: approach in `<md>`, file changes use `change` attribute (add/edit/delete), keep it high-level
  - Verify: guidelines are clear and consistent with solution.md §D stage 3.

- [ ] Step B.7: Write `src/beta-planning/refs/tab-plan.md` — content guidelines for the Plan tab:
  - Sections: Summary (`<pd-section id="summary">`), Execution Sequence (`<pd-mermaid>`), Phase Stepper (`<pd-stepper>` with `<pd-phase>` elements), Success Criteria (`<pd-section id="success-criteria">`)
  - Rules: each pd-phase has `n`, `title`, `files` (comma-sep paths matching pd-files), `status="todo"`, body in `<md>`. Phases are atomic. Backfill `<pd-ac>` cards' `phases` and `tests` attributes in the Verification tab.
  - Verify: guidelines are clear and consistent with solution.md §E.

- [ ] Step B.8: Write `src/beta-planning/refs/template-context.md` — same rules as current `src/planning-workflow/refs/template-context.md`:
  - Key Files (path:line with descriptions), Patterns, Related Tasks
  - Only verified codebase facts, full paths, excerpts only
  - Verify: content matches current template conventions.

- [ ] Step B.9: Commit: `feat(002): phase B — beta-planning reference files`
  - Verify: all 7 ref files exist in `src/beta-planning/refs/`.

### Phase C: Beta-planning module — skill templates

- [ ] Step C.1: Write `src/beta-planning/skills/beta-new-task/SKILL.md`:
  - Frontmatter: `name: beta-new-task`, description with trigger phrases
  - Link to `[references/beta-workflow-overview.md](references/beta-workflow-overview.md)`
  - Process steps: scan skills, read project docs, determine ID, derive name, create folder, create plan.html from boilerplate (per `[references/html-boilerplate.md](references/html-boilerplate.md)`), populate Requirements tab (per `[references/tab-requirements.md](references/tab-requirements.md)`), resolve open questions, hard-stop with `{{ skill:beta-new-solution }}` reference
  - Guiding principles (same as current new-task: ask don't guess, push back on unclear)
  - Verify: frontmatter valid, all `{{ skill:X }}` refs will resolve, all `[references/X]` match DSL declarations.

- [ ] Step C.2: Write `src/beta-planning/skills/beta-new-solution/SKILL.md`:
  - Frontmatter: `name: beta-new-solution`, description with trigger phrases
  - Link to `[references/beta-workflow-overview.md](references/beta-workflow-overview.md)`
  - Process steps split into 3 stages:
    - Stage 1: Read plan.html Requirements tab, spawn CB1/CB2 subagents, write context.md (per `[references/template-context.md](references/template-context.md)`)
    - Stage 2: Scan skills for verification approaches, write Verification tab (per `[references/tab-verification.md](references/tab-verification.md)`), hard-stop for review
    - Stage 3: Assess complexity, explore options if ambiguous, write Solution tab (per `[references/tab-solution.md](references/tab-solution.md)`), validate assumptions, hard-stop with `{{ skill:beta-new-plan }}` reference
  - Guiding principles (same as current new-solution: simplest approach, surface tradeoffs)
  - Verify: frontmatter valid, all refs match DSL, two explicit hard-stops in process.

- [ ] Step C.3: Write `src/beta-planning/skills/beta-new-plan/SKILL.md`:
  - Frontmatter: `name: beta-new-plan`, description with trigger phrases
  - Link to `[references/beta-workflow-overview.md](references/beta-workflow-overview.md)`
  - Process steps: read plan.html + context.md, enrich context with git history (CB3 subagent), write Plan tab (per `[references/tab-plan.md](references/tab-plan.md)`), backfill pd-ac traceability attributes in Verification tab, hard-stop telling user the planning phase is complete and to commit manually (since `/commit-task` and `/review-task` don't support beta HTML format yet)
  - Verify: frontmatter valid, all refs match DSL, backfill step is explicit.

- [ ] Step C.4: Register module in `src/compile.py` `__main__` block:
  ```python
  beta_planning = module("beta-planning",
      skill("beta-new-task",     refs=[ref("beta-workflow-overview.md"), ref("html-boilerplate.md"),
                                       ref("tab-requirements.md")]),
      skill("beta-new-solution", refs=[ref("beta-workflow-overview.md"), ref("tab-verification.md"),
                                       ref("tab-solution.md"), ref("template-context.md")]),
      skill("beta-new-plan",     refs=[ref("beta-workflow-overview.md"), ref("tab-plan.md")]),
  )
  ```
  Add `beta_planning` to the `compile([...])` call.
  - Verify: `make compile` succeeds, `skills/beta-new-task/SKILL.md`, `skills/beta-new-solution/SKILL.md`, `skills/beta-new-plan/SKILL.md` are produced with references copied.

- [ ] Step C.5: Verify `{{ skill:X }}` substitution in compiled output:
  - Check `skills/beta-new-task/SKILL.md` — hard-stop message contains literal `beta-new-solution` (not the `{{ skill:... }}` tag)
  - Check `skills/beta-new-task/references/beta-workflow-overview.md` — pipeline diagram contains literal skill names (refs were substituted)
  - Verify: no `{{ skill:` patterns remain in any compiled output under `skills/beta-*/`.

- [ ] Step C.6: Run `autoskill lint` on the three new skills.
  - Verify: all pass without errors.

- [ ] Step C.7: Commit: `feat(002): phase C — beta-planning skill templates`
  - Verify: `make check` passes (compile + lint).

### Phase D: Planning-doc update + final validation

- [ ] Step D.1: Edit `src/rich-docs/skills/planning-doc/SKILL.md`:
  - Add a pd-meta preservation rule in the authoring rules section (or as a new bullet near "Content is edited in place; threads are APPEND-ONLY"): "Preserve `<script type="application/json" id="pd-meta">` blocks when editing existing docs. Never modify, move, or delete the pd-meta block — it tracks task lifecycle state managed by the planning workflow."
  - Bump the emergency cheat-sheet pin from `pd-v0.2.0` to `pd-v0.3.0` (line 92) to match the current release.
  - Verify: rule is clear, cheat-sheet pin matches `pd-components/dist/llms.txt` release tag, doesn't conflict with existing content.

- [ ] Step D.2: Recompile to pick up planning-doc change: `make compile`.
  - Verify: `skills/planning-doc/SKILL.md` contains the new preservation rule. All other skills unchanged.

- [ ] Step D.3: End-to-end validation:
  - `make check` passes (compile + lint)
  - Compiled `skills/beta-new-task/SKILL.md` is under 15,000 chars
  - Compiled `skills/beta-new-solution/SKILL.md` is under 15,000 chars
  - Compiled `skills/beta-new-plan/SKILL.md` is under 15,000 chars
  - All `{{ skill:X }}` references resolved in compiled output (grep for `{{ skill:` returns nothing in `skills/`)
  - Verify: `grep -r '{{ skill:' skills/` returns no matches.

- [ ] Step D.4: Install skills: `make install`
  - Verify: install script runs, new skills available in agents.

- [ ] Step D.5: Commit: `feat(002): phase D — planning-doc pd-meta rule + final validation`
  - Verify: `make check` passes, clean git status.

## Success Criteria
- [ ] `make compile` produces `skills/beta-new-task/`, `skills/beta-new-solution/`, `skills/beta-new-plan/` with all references (AC-1)
- [ ] `{{ skill:X }}` resolves to skill names in compiled templates AND refs; renaming in DSL propagates (AC-2)
- [ ] Invalid/ambiguous `{{ skill:X }}` fails compilation with clear error naming the module, skill, and unresolved reference (AC-3)
- [ ] `grep -r '{{ skill:' skills/` returns zero matches (all directives resolved)
- [ ] All three compiled skills are under 15,000 chars
- [ ] `autoskill lint` passes for all new skills
- [ ] `planning-doc` skill includes pd-meta preservation rule

## Open Questions
- (none)
