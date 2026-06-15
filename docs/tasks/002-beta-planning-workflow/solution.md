# Solution: Task 002

New `src/beta-planning/` compiler module with three skills (`beta-new-task`, `beta-new-solution`, `beta-new-plan`) that produce a single `plan.html` + `context.md` per task, plus a compiler extension (`{{ skill:X }}`) for rename-safe inter-skill references. See [context.md](./context.md) for the codebase facts this builds on.

## Approach

### A. Compiler extension: `{{ skill:X }}` directive

1. Add `SKILL_REF_PATTERN = re.compile(r"\{\{\s*skill:(.+?)\s*\}\}")` near `src/compile.py:48`. Note: **not** line-anchored (unlike `REF_PATTERN`), because skill references appear inline in sentences.

2. **Phase 1 validation** — after existing cross-checks (line ~128), extract all `{{ skill:X }}` matches from template content. Build a lookup of all skill names across all modules. For each match:
   - Bare name (e.g. `{{ skill:beta-new-solution }}`) → look up across all modules. If the name exists in exactly one module, resolve. If it exists in multiple modules, **error and require the qualified form** (no implicit same-module preference — explicit over implicit).
   - Qualified name (e.g. `{{ skill:rich-docs/planning-doc }}`) → resolve in named module. Error if module or skill not found.
   - Also scan ref file contents for `{{ skill:X }}` patterns and validate those too.

3. **Phase 2 rendering** — after `REF_PATTERN.sub(replace_ref, content)` (line 163), add a second pass:
   ```python
   def replace_skill_ref(m: re.Match) -> str:
       raw = m.group(1).strip()
       if "/" in raw:
           mod_name, skill_name = raw.split("/", 1)
       else:
           skill_name = raw  # already validated in Phase 1
       return skill_name
   rendered = SKILL_REF_PATTERN.sub(replace_skill_ref, rendered)
   ```
   The output is the skill's compiled name — today `beta-new-solution`, after rename just `new-solution`.

4. **Ref copying with substitution** — change the ref copy step (lines 180-187). Instead of `shutil.copy2`, read each ref, check for `SKILL_REF_PATTERN`. If found, substitute and write; if not, `shutil.copy2` as before (preserves timestamps for unchanged files, avoids unnecessary writes).

### B. New module: `src/beta-planning/`

```
src/beta-planning/
  refs/
    beta-workflow-overview.md       # pipeline diagram (uses {{ skill:X }})
    html-boilerplate.md             # starting HTML structure for plan.html
    tab-requirements.md             # content guidelines for Requirements tab
    tab-verification.md             # content guidelines for Verification tab
    tab-solution.md                 # content guidelines for Solution tab
    tab-plan.md                     # content guidelines for Plan tab
    template-context.md             # same rules as current context template
  skills/
    beta-new-task/SKILL.md
    beta-new-solution/SKILL.md
    beta-new-plan/SKILL.md
```

DSL registration:
```python
beta_planning = module("beta-planning",
    skill("beta-new-task",     refs=[ref("beta-workflow-overview.md"), ref("html-boilerplate.md"),
                                     ref("tab-requirements.md")]),
    skill("beta-new-solution", refs=[ref("beta-workflow-overview.md"), ref("tab-verification.md"),
                                     ref("tab-solution.md"), ref("template-context.md")]),
    skill("beta-new-plan",     refs=[ref("beta-workflow-overview.md"), ref("tab-plan.md")]),
)
```

### C. `beta-new-task` skill

Process (mirrors current `new-task` but outputs HTML):

1. Scan skills, read project docs, determine task ID, derive name, create folder.
2. Create `plan.html` from the boilerplate template with:
   - `<script type="application/json" id="pd-meta">` in `<head>` with full schema (nulls for unknown fields).
   - `<pd-doc>` shell with `status="draft"` and `pr="pending"`.
   - Single `<pd-tab name="Requirements">` containing:
     - `<pd-section id="problem" title="Problem">` — with `<md>` body.
     - `<pd-section id="goals" title="Goals">` — bullet list in `<md>`.
     - `<pd-section id="out-of-scope" title="Out of Scope">` — in `<md>`.
     - `<pd-section id="open-questions" title="Open Questions">` — in `<md>`.
   - No `<pd-ac>` cards yet — acceptance criteria move to the Verification tab.
3. Resolve open questions interactively (same as current).
4. Hard-stop: "Review plan.html. When ready, run `/{{ skill:beta-new-solution }}` to continue."

### D. `beta-new-solution` skill

Process (three sub-stages with two review gates):

**Stage 1: Context gathering**
1. Read `plan.html` Requirements tab. Verify open questions resolved.
2. Spawn 2 parallel subagents (same CB1/CB2 pattern as current `new-solution`).
3. Write `context.md` in the task folder (same format/rules as current template).

**Stage 2: Verification tab** (new first-class stage)
1. Scan available project skills for testing/verification/assurance strategies. Load any matched skills.
2. Using the context + requirements, design the verification strategy:
   - `<pd-section id="test-strategy" title="Test Strategy">` — approach, tooling, coverage philosophy in `<md>`.
   - `<pd-mermaid>` — coverage architecture diagram (when useful; e.g. mapping test types to system layers).
   - `<pd-ac>` cards — one per acceptance criterion, with `id`, `title`, and Given/When/Then in `<md>` body. Leave `phases` and `tests` attributes empty (filled later by Plan stage).
   - `<pd-section id="verification-gaps" title="Known Gaps & Risks">` — what isn't covered and why.
3. Insert `<pd-tab name="Verification">` into plan.html (after Requirements tab).
4. **Review gate 1**: Hard-stop. "Review the Verification tab. When ready, confirm to proceed to Solution design."

**Stage 3: Solution tab**
1. Assess complexity. If ambiguous, explore options with parallel subagents and present comparison.
2. Design the solution and insert `<pd-tab name="Solution">` with:
   - `<pd-section id="approach" title="Approach">` — high-level steps in `<md>`.
   - `<pd-files>` — file-change tree with `<pd-file path change>` entries.
   - `<pd-section id="rejected-alternatives" title="Rejected Alternatives">` — in `<md>`.
   - `<pd-decisions>` — auto-generated decision log (picks up any threads from earlier tabs).
3. Validate assumptions with user (same pattern as current).
4. **Review gate 2**: Hard-stop. "Review the Solution tab. When ready, run `/{{ skill:beta-new-plan }}` to continue."

### E. `beta-new-plan` skill

Process:

1. Read plan.html (all tabs) + context.md.
2. Enrich context.md with git history (same CB3 subagent as current `new-plan`).
3. Design execution phases and insert `<pd-tab name="Plan">` with:
   - `<pd-section id="summary" title="Summary">` — one sentence in `<md>`.
   - `<pd-mermaid caption="Execution Sequence">` — phase dependency DAG.
   - `<pd-stepper>` with `<pd-phase>` elements — each phase has `n`, `title`, `files` (comma-separated paths matching pd-files), `status="todo"`. Body contains step descriptions in `<md>`.
   - `<pd-section id="success-criteria" title="Success Criteria">` — maps back to `<pd-ac>` ids.
4. **Back-fill traceability**: update `<pd-ac>` cards in the Verification tab — set their `phases` attribute to the phase numbers that cover them, and `tests` attribute to test file paths from the solution.
5. Hard-stop: "Review the Plan tab. The beta workflow's planning phase is now complete. Commit the task folder (`docs/tasks/$ID-$NAME/`) manually when ready — `/commit-task` and `/review-task` do not yet support the beta HTML format."

<!-- RESOLVED(P1): The beta-new-plan hand-off points to skills that will reject beta artifacts
REVIEW: This hard-stop directs the user to /review-task and /commit-task. Verified src/planning-workflow/skills/commit-task/SKILL.md:22 gates on "All 4 files exist: requirements.md, solution.md, context.md, plan.md" and checks Open Questions in requirements.md/plan.md. A beta task has only plan.html + context.md, so commit-task's completeness check fails outright. /review-task likewise reads the 4 markdown files (review-task SKILL.md:21). Pointing users here is a dead end until those skills are beta-aware. Either build a beta finalize path or change the hand-off message to reflect what actually works today.
AUTHOR: Changed the hard-stop message to tell the user to commit manually and explicitly state that /commit-task and /review-task don't support beta HTML format yet. This is honest about the soft-launch state — downstream skill adaptation is a documented follow-up.
-->


### F. Structured metadata: `pd-meta` JSON block

Located in `<head>` as `<script type="application/json" id="pd-meta">`:

```json
{
  "id": "002",
  "name": "beta-planning-workflow",
  "status": "planning",
  "branch": null,
  "epic": null,
  "created": "2026-06-15",
  "pr": null
}
```

**Status lifecycle:**
- `"planning"` — set on creation by `beta-new-task`
- `"executing"` — set by `execute-task` when it creates the worktree/branch (also populates `branch`)
- `"merged"` — set by `complete-task` on merge (also populates `pr`)

**Relationship to `<pd-doc>` attributes:**
- `pd-doc status` (draft/in-review/approved) = document review state
- `pd-meta status` (planning/executing/merged) = task lifecycle state
- These are complementary — a doc can be "approved" while the task is still "planning" (approved docs, not yet executing)

### G. Review via pd-threads

The HTML structure supports pd-thread review conversations:
- `<pd-thread anchor="section-id" priority="p1|p2|p3" title="Short summary">` placed after the anchored element.
- Initial `<pd-comment by="review">` with the concern.
- Author resolves by appending `<pd-comment by="author">` and setting `status="resolved"` or `"rejected"`.
- `<pd-decisions>` in the Solution tab auto-surfaces all resolved threads.

**Note:** The existing `/review-task` and `/request-claude-review` skills are NOT beta-aware — they read the 4 markdown files and emit `<!-- UNRESOLVED(...) -->` comments. Teaching them to read plan.html and emit pd-threads requires changing their I/O contract (file discovery, tab parsing, output format). This is deferred to the downstream integration follow-up task. For now, reviews on beta tasks are done manually or via the planning-doc comment export/merge protocol.

<!-- RESOLVED(P1): "No changes to the review skills" is contradicted by the actual skill source
REVIEW: src/planning-workflow/skills/review-task/SKILL.md:21 hard-codes "Read ALL docs: requirements.md, solution.md, context.md, plan.md" and its output protocol writes `<!-- UNRESOLVED(...) -->` markdown comments (including a clean-review comment "at the top of plan.md"). For a beta task none of those files exist — only plan.html + context.md — and the protocol is markdown, not pd-thread. So the claim that the only adaptation is "writing <pd-thread> instead of markdown" actually requires non-trivial changes: teaching the skill to find plan.html, parse tabs, and emit pd-thread elements. The "adaptation" is the whole I/O contract of the skill. Either scope a beta-aware review path or acknowledge review-task must change (which conflicts with requirements Out of Scope). See [requirements.md](./requirements.md) AC-7.
AUTHOR: Removed the incorrect claim. Now explicitly states that review skills are NOT beta-aware and that integration is deferred. The manual review path (planning-doc comment export/merge) works today without skill changes.
-->


### H. Planning-doc skill: pd-meta awareness

<!-- RESOLVED(P3): planning-doc cheat sheet pins an older pd-components tag
REVIEW: This task pins beta plan.html to pd-v0.3.0 (matches pd-components/dist/llms.txt:8, current release). But the file you're editing here, src/rich-docs/skills/planning-doc/SKILL.md:92, still pins its emergency cheat sheet to pd-v0.2.0. Since you're already touching this file for the pd-meta rule, consider bumping the cheat-sheet pin to pd-v0.3.0 so the two don't drift. Minor / optional.
AUTHOR: Good catch. Will bump the cheat-sheet pin to pd-v0.3.0 in the same edit (Phase D, Step D.1). Added to plan.md.
-->

Update the `planning-doc` skill to recognize and preserve `<script type="application/json" id="pd-meta">` when editing existing HTML docs that contain it. This ensures the planning-doc skill doesn't strip or corrupt the meta block when it edits a beta-planning doc (e.g. for comment merging or general doc updates). The planning-doc skill doesn't need to *create* pd-meta blocks — only preserve them.

## Files

```
+ src/beta-planning/refs/beta-workflow-overview.md       # pipeline diagram with {{ skill:X }} refs
+ src/beta-planning/refs/html-boilerplate.md             # starting HTML structure
+ src/beta-planning/refs/tab-requirements.md             # Requirements tab content guidelines
+ src/beta-planning/refs/tab-verification.md             # Verification tab content guidelines
+ src/beta-planning/refs/tab-solution.md                 # Solution tab content guidelines
+ src/beta-planning/refs/tab-plan.md                     # Plan tab content guidelines
+ src/beta-planning/refs/template-context.md             # context.md template (same rules as current)
+ src/beta-planning/skills/beta-new-task/SKILL.md        # task creation skill
+ src/beta-planning/skills/beta-new-solution/SKILL.md    # solution + verification skill
+ src/beta-planning/skills/beta-new-plan/SKILL.md        # plan skill
~ src/compile.py                                         # add SKILL_REF_PATTERN, validation, substitution in templates + refs
~ src/CLAUDE.md                                          # document {{ skill:X }} directive
~ src/rich-docs/skills/planning-doc/SKILL.md             # add pd-meta preservation rule
```

## Test Coverage

| AC  | Test Type   | File / Method                                   |
|-----|-------------|-------------------------------------------------|
| AC-1 | integration | `make compile` — beta-planning module compiles  |
| AC-2 | integration | compile with `{{ skill:X }}`, rename in DSL, recompile — output changes |
| AC-3 | integration | compile with `{{ skill:bad-module/bad-skill }}` — fails with clear error |
| AC-4 | manual      | invoke `/beta-new-task`, verify plan.html structure + meta block |
| AC-5 | manual      | invoke `/beta-new-solution`, verify 3 sub-stages + 2 gates |
| AC-6 | manual      | invoke `/beta-new-plan`, verify Plan tab + AC traceability backfill |
| AC-7 | manual      | insert pd-thread into plan.html, verify rendering + decisions log |
| AC-8 | manual      | inspect pd-meta block after `/beta-new-task` — all fields present, status="planning", nulls correct |
| AC-9 | manual      | have an agent read plan.html and identify tab content + plan phases |

## Out of Scope

- Changes to existing `planning-workflow` module skills (they continue unchanged).
- Downstream skill adaptation (`execute-task`, `complete-task`) — beta integration is follow-up.
- New pd-components — use existing library as-is.
- Automated tests beyond compiler integration — skill behavior is tested manually.
- Migration tooling for converting old tasks to new format.

## Rejected Alternatives

- **Single-file with context embedded in HTML**: rejected because context.md is agent-consumed reference data that changes with the codebase. Embedding it in HTML wastes tokens for human readers and makes it harder for executors to extract.
- **Separate HTML file per stage (requirements.html, solution.html, etc.)**: rejected because the whole point is consolidation — one doc with tabs is more navigable and keeps review threads co-located.
- **Using pd-doc `status` attribute for task lifecycle**: rejected because pd-doc status (draft/in-review/approved) tracks document review state, which is a different axis from task lifecycle (planning/executing/merged). They're complementary.
- **Positional/alias-based `{{ skill: }}` resolution** (e.g. `{{ skill:next }}`): rejected because explicit names are clearer, greppable, and the compile-time validation catches breakage immediately on rename. The bounded scope (all within one module's source) makes updates trivial.
- **Recursive ref expansion** (making `{{ ref:X }}` work inside refs): rejected as overkill. Only `{{ skill:X }}` needs to work in refs (simple string substitution), not full file inlining.
- **Acceptance criteria in Requirements tab** (as in current workflow): rejected. ACs benefit from codebase context (knowing what's testable, what patterns exist) so they're authored during the Verification stage after context gathering. Requirements tab stays focused on problem/goals/scope — the "what and why", not "how we'll prove it".
