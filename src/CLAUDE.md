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

SKILL.md files support one directive:

- `{{ ref:<filename> }}` — replaced with the full contents of `refs/<filename>` from the same module. The referenced file is also copied to `references/<filename>` in the compiled output.

The `{{ ref: }}` tag must appear on its own line. It is replaced inline (no extra wrapping).

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

## Pre-compile checks

- All ref files referenced in the DSL exist in the module's `refs/` directory
- All skill template files exist in the module's `skills/<name>/` directory
- Every `{{ ref:X }}` tag in a template has a corresponding ref in the DSL declaration
- Every ref in the DSL declaration is actually used by a `{{ ref:X }}` tag in the template (warn, don't fail)
- YAML frontmatter in each SKILL.md contains required fields: `name`, `description`
- Final rendered output is under the size limit
