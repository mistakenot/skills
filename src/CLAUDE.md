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

- `{{ skill:<name> }}` — replaced with the compiled skill name. Appears inline (not line-anchored) — typically used mid-sentence, e.g. `run /{{ skill:new-solution }}`. Works in both SKILL.md templates and ref files.

  **Resolution rules:**
  - Bare name (e.g. `{{ skill:new-solution }}`) — resolves if the skill exists in exactly one module. If the name exists in multiple modules, the compiler errors and requires the qualified form.
  - Qualified name (e.g. `{{ skill:rich-docs/planning-doc }}`) — resolves in the named module. Errors if the module or skill is not found.

  **Validation:** The compiler validates all `{{ skill:X }}` references in Phase 1 (before writing any output). Unknown skills, unknown modules, and ambiguous bare names all produce errors.

- `{{ pd-version }}` — replaced with the current pd-components release tag (e.g. `pd-v0.4.0`), read from `pd-components/package.json` at compile time. Appears inline. Works in both SKILL.md templates and ref files.

- `{{ index:techniques }}` — replaced with a generated markdown table of all technique cards declared for the skill. Columns: Technique, What it catches, Oracle, Archetypes, Crit, Volatility, Link. The table is built from each `technique-*.md` card's frontmatter at compile time.

Technique cards follow the `technique-<slug>.md` naming convention and live in the module's `refs/` directory. Each card has flat frontmatter with 13 required keys (`name`, `summary`, `oracle`, `archetypes`, `criticality-min`, `volatility-fit`, `harness`, `pairs-with`, `upgrade-looser`, `upgrade-stricter`, `cost-author`, `cost-maintain`, `cost-run`) and 12 exact-title `## ` sections validated at compile time. Missing keys, missing sections, or out-of-order sections fail the build.

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

## `sk` CLI generation

The compiler also generates `sk.sh` at the repo root — a standalone, self-updating wrapper around `npx skills@latest` meant to be copied to `~/.local/bin/sk`. It's installed as `sk` rather than `skills` because the bare `skills` name belongs to the npm CLI it delegates to (`$(which skills)` → `node_modules/skills/bin/cli.mjs`); installing as `skills` would clobber that binary.

```bash
curl -fsSL https://raw.githubusercontent.com/mistakenot/skills/main/sk.sh -o ~/.local/bin/sk && chmod +x ~/.local/bin/sk

sk ls                       # list packages (one per module)
sk add planning-workflow    # install a package's skills ('all' for everything)
sk update                   # update all installed skills
```

Like `install.sh`, the package→skill mappings (and package descriptions) are baked in at compile time from the DSL, so the CLI never drifts. The difference is the self-update step: on every run the script fetches its own latest version from `CLI_SELF_URL` (raw GitHub, `main` branch, `sk.sh`) and, if it differs, overwrites itself in place and asks the user to re-run. This keeps the baked-in mappings fresh without a package manager. Self-update fails open (offline / no `curl` / non-writable → skip).

Testing/escape-hatch env vars (also shown in `sk help`): `SKILLS_DRY_RUN=1` prints the `npx` commands instead of running them (and skips self-update), `SKILLS_NO_SELFUPDATE=1` disables the update check, `SKILLS_SELF_URL` repoints the update source (e.g. a fork), and `SKILLS_AGENTS` overrides the default `claude-code codex` target agents. The generator lives in `_generate_cli_script` / `_CLI_TEMPLATE` in `compile.py`.

## Claude Code plugin + marketplace generation

The compiler also packages the repo as a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugins-reference), so users can install skills via `/plugin` without the `npx skills` flow. Each **module maps to one plugin**; the repo root is the marketplace.

It emits (all regenerated from scratch each compile, so they never drift from the DSL):

- `.claude-plugin/marketplace.json` — lists every module as a plugin entry (`name`, `source`, `description`, `category`).
- `plugins/<module>/.claude-plugin/plugin.json` — the plugin manifest (`name`, `description`, `author`, `keywords`, …).
- `plugins/<module>/skills/<skill>/` — a **copy** of each compiled skill (`SKILL.md` + `references/`).

Module metadata for the manifests comes from the DSL: `module()` accepts `description`, `category`, `keywords`, and `display_name` keyword args. Marketplace-level constants (`MARKETPLACE_NAME`, `OWNER`, etc.) live near `_generate_plugins` in `compile.py`.

**Versioning:** the `version` field is intentionally omitted, so Claude Code versions each plugin by git commit SHA — consumers pick up changes on every commit with no manual bump. (`claude plugin validate --strict` will warn about the missing version; this is expected.)

Install flow for consumers:

```bash
/plugin marketplace add mistakenot/skills
/plugin install planning-workflow@mistakenot-skills
```

Skills installed this way are namespaced as `<module>:<skill>` (e.g. `planning-workflow:new-task`).

## Pre-compile checks

- All ref files referenced in the DSL exist in the module's `refs/` directory
- All skill template files exist in the module's `skills/<name>/` directory
- Every `{{ ref:X }}` tag in a template has a corresponding ref in the DSL declaration
- Every ref in the DSL declaration is actually used by a `{{ ref:X }}` tag in the template (warn, don't fail)
- Every `{{ skill:X }}` tag in templates and ref files resolves to a known skill (error on unknown or ambiguous)
- YAML frontmatter in each SKILL.md contains required fields: `name`, `description`
- Final rendered output is under the size limit
