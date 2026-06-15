# `src`

This folder contains compilable skills. This is useful because sometimes multiple skills want to share the same docs and references.

Instead of having drift when updates happen, we have a simple framework for compiling our skills via a python DSL.

## Directory structure

```
src/
  planning-workflow/              # module — a group of related skills
    refs/
      communicate-during-plan-reviews.md
    skills/
      review-task/
        SKILL.md                  # supports {{ ref:filename }} templating
      resolve-comments/
        SKILL.md
  compile.py                      # DSL + compiler
```

Output goes to `./skills/` at the repo root:

```
skills/
  review-task/
    SKILL.md
    references/
      communicate-during-plan-reviews.md
  resolve-comments/
    SKILL.md
    references/
      communicate-during-plan-reviews.md
```

## Module conventions

- Each module is a directory under `src/` (excluding `compile.py` and `CLAUDE.md`).
- `refs/` contains shared reference files available to all skills in the module.
- `skills/<name>/SKILL.md` is the template for each skill. It must have YAML frontmatter with `name` and `description`.
- Skills can include additional files beyond SKILL.md (e.g. their own local references not shared with other skills).

## Templating

SKILL.md files support two directives:

- `{{ ref:<filename> }}` — replaced with the full contents of `refs/<filename>` from the same module. The referenced file is also copied to `references/<filename>` in the compiled output. Must appear on its own line (line-anchored).

- `{{ skill:<name> }}` — replaced with the compiled skill name. Appears inline (not line-anchored) — typically used mid-sentence, e.g. `run /{{ skill:beta-new-solution }}`. Works in both SKILL.md templates and ref files.

  **Resolution rules:**
  - Bare name (e.g. `{{ skill:beta-new-solution }}`) — resolves if the skill exists in exactly one module. If the name exists in multiple modules, the compiler errors and requires the qualified form.
  - Qualified name (e.g. `{{ skill:rich-docs/planning-doc }}`) — resolves in the named module. Errors if the module or skill is not found.

  **Validation:** The compiler validates all `{{ skill:X }}` references in Phase 1 (before writing any output). Unknown skills, unknown modules, and ambiguous bare names all produce errors.

## DSL (compile.py)

The DSL declares modules, their skills, and which refs each skill uses. Example:

```python
from compiler import module, skill, ref

planning_workflow = module("planning-workflow",
    skill("review-task", refs=[ref("communicate-during-plan-reviews.md")]),
    skill("resolve-comments", refs=[ref("communicate-during-plan-reviews.md")]),
)

compile([planning_workflow])
```

The `compile()` function:
1. Validates that all referenced files exist (refs, skill templates)
2. Validates that every `{{ ref:X }}` in a SKILL.md has a matching ref declaration
3. Warns if a declared ref is unused by the skill template
4. Checks that the final rendered SKILL.md is under a size limit (default 15,000 chars) to avoid bloated skill files
5. Renders templates and copies refs to `./skills/<name>/`

## Install script generation

The compiler also generates `install.sh` at the repo root. This script lets downstream consumers install all skills or a specific module:

```bash
./install.sh                              # all skills
./install.sh --module planning-workflow   # just planning skills
./install.sh --agent claude-code          # override target agents
```

The module→skill mappings are baked into the case block at compile time, so the script is always in sync with the DSL declarations. The repo slug is set via the `REPO` constant in `compile.py`.

## Pre-compile checks

- All ref files referenced in the DSL exist in the module's `refs/` directory
- All skill template files exist in the module's `skills/<name>/` directory
- Every `{{ ref:X }}` tag in a template has a corresponding ref in the DSL declaration
- Every ref in the DSL declaration is actually used by a `{{ ref:X }}` tag in the template (warn, don't fail)
- Every `{{ skill:X }}` tag in templates and ref files resolves to a known skill (error on unknown or ambiguous)
- YAML frontmatter in each SKILL.md contains required fields: `name`, `description`
- Final rendered output is under the size limit
