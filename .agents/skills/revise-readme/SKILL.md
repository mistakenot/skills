---
name: revise-readme
description: "Update README and documentation to reflect all recent changes. Use when new features, commands, or options have been added and docs need to catch up. Frames everything as current state — never references what changed."
---

# Revise README

Update the README and other project documentation to accurately reflect the current state of the project.

## Process

1. **Inventory recent changes** — Check git log, diff against main, and scan for new/modified features, commands, options, configuration, skills, or modules that may not yet be documented.

2. **Audit existing docs** — Read the current README and any other documentation files. Identify gaps where new functionality is missing, outdated descriptions that no longer match reality, or structural issues (e.g., a new section is needed).

3. **Update documentation** — Edit all relevant documentation files to reflect the current state of the project. This includes:
   - New commands, options, or features
   - New modules, skills, or components
   - Changed installation or usage instructions
   - Updated examples or descriptions
   - Corrected or removed stale information

4. **Verify completeness** — Re-read the updated docs and cross-check against the actual project structure to ensure nothing was missed. Every feature, command, option, and configuration that exists in the project should appear in the docs. If it exists, it gets documented — no exceptions.

## README Structure

A good README flows from quick orientation to full reference. Follow this order:

1. **Summary** — One or two sentences: what the project is and what it does.
2. **Quickstart / Installation** — The fastest path from zero to working. Minimal steps, copy-pasteable commands.
3. **End-to-end examples** — A few complete, realistic usage examples that show the main workflows. These orient the reader before diving into details.
4. **Reference manual** — Exhaustive documentation of every feature, command, option, flag, and configuration. This is where completeness matters most. Every capability gets its own entry with a description and usage example.

When updating an existing README, preserve this general flow. If the README doesn't follow this structure yet, migrate toward it incrementally — don't reorganize wholesale unless the current layout is actively confusing.

## Writing Rules

- **Present tense, current state only.** Never say "we added X", "X is now Y", "new in v2", or any phrasing that implies a before/after. Describe the system as it is — as if it were always this way.
- **Be exhaustive in the reference sections.** Document every feature, command, option, and configuration. Add usage examples for all non-trivial features. Treat each update as a full-coverage pass — don't just patch in the new thing, verify that existing features are equally well-documented.
- **Match the existing tone and style.** If the README uses terse bullet points, keep that style. If it uses full paragraphs, match that.
- **Preserve existing structure where possible.** Add new sections or entries in the logical place within the existing document structure. Don't reorganize unless the current structure can't accommodate the new content.
- **Be specific.** Include actual command names, flag names, file paths, and concrete examples — not vague descriptions.
- **Don't pad.** If a feature is simple, a one-liner is fine. Don't inflate descriptions to seem thorough.
