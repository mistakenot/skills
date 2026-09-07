---
name: revise-readme
description: "Updates README and docs to match the current project: every command, option and feature, install and getting-started sections, mermaid diagrams. Use when 'update the readme', 'revise docs', 'docs are stale'. Current state only."
---

# Revise README

Bring the README and other project documentation into line with what the
project actually does today. The goal is a README a new user can trust: every
user-facing feature is in it, every example in it runs, and nothing in it
describes a version that no longer exists.

## Process

1. **Inventory the real surface, from source.** Documentation goes stale
   because it is written from memory. Build the list of what exists from the
   artefacts themselves, not from recollection or from the old README:
   - CLI commands and flags: run `--help` on the binary and each subcommand,
     or read the argument parser. Every command and flag that appears there
     is user-facing and must be documented.
   - Config: env vars, config files, defaults, and the precedence order when
     several sources apply.
   - Entry points: Makefile targets, npm scripts, install scripts, exported
     APIs, skills or plugins the project ships.
   - Recent change: `git log` and the diff against main, to find features
     whose docs were never written.

2. **Audit the existing docs against that inventory.** Read the README and
   every other doc file. Produce three lists: features with no docs, docs
   that describe something differently from how it behaves now, and docs
   for things that no longer exist. The third list matters as much as the
   first; a stale section misleads more readers than a missing one.

3. **Update the docs.** Add the missing entries, correct the wrong ones,
   and delete the dead ones, including dead links and references to removed
   flags or renamed commands. Follow the structure and writing rules below.

4. **Verify every example runs.** Each command block in the README is
   executed, or at minimum parsed against `--help`, before it is kept. An
   example that errors teaches the reader to distrust the whole document.
   Render every mermaid diagram (with `mmdc` if available, otherwise a
   syntax check) so a broken diagram never lands.

5. **Check the diff is docs-only.** A documentation pass must not touch
   code, config or tests. If verifying an example revealed a real bug,
   report it rather than fixing it here.

6. **Commit** the changed documentation files with a concise present-tense
   message ("Update README with X documentation"). Do not push unless asked.

7. **Report what you could not verify.** In the final message, list any
   documented behaviour you described without running it, so the user can
   spot-check exactly those claims.

## README structure

A README flows from orientation to full reference. Follow this order and,
when updating an existing README, migrate toward it incrementally rather
than reorganising wholesale.

1. **Summary.** One or two sentences: what the project is and what it does.

2. **Installation.** When the project is designed to be installed, give the
   full path from zero: prerequisites and supported platforms, the install
   command for each supported method, how to verify it worked, and how to
   upgrade and uninstall. Upgrade and uninstall are the sections most often
   missing and most often searched for.

3. **Getting started.** For a CLI, a short multi-line shell session that
   walks through the main workflow, with a comment above each command
   saying what it does and why the reader is running it:

   ```bash
   # Initialise a project config in the current directory
   tool init --project

   # Add a source; the lock file records the exact version fetched
   tool add org/repo --name thing

   # Render everything the lock file lists into the target directories
   tool sync
   ```

   For a library, the equivalent is a minimal end-to-end code example.

4. **Concepts.** When the project has vocabulary of its own (its nouns,
   modes, lifecycle states), define each term once here before the
   reference uses it. If the repo keeps a glossary (for example
   `docs/concepts/UBIQUITOUS_LANGUAGE.md`), summarise and link rather than
   duplicate.

5. **Architecture and structure.** Use mermaid diagrams where the
   complexity justifies one; a three-component project needs a sentence,
   not a diagram. Rules that keep diagrams readable:
   - One diagram per concern. Split a single complex diagram into several
     small ones (components, data flow, lifecycle) rather than one that
     shows everything.
   - Roughly eight nodes or fewer per diagram. Past that, split again.
   - `flowchart` for structure and dependencies, `sequenceDiagram` for
     runtime interactions, `stateDiagram-v2` for lifecycles.
   - Label edges with what flows along them, not just that something does.
   - Introduce each diagram with a sentence saying what question it answers.

   Show project layout as a file-tree block generated from the actual tree
   (`tree -L 2` or `find`), trimmed to the directories a user needs to know
   about, with a short comment per entry. A generated tree cannot lie about
   files that do not exist.

6. **Reference.** Exhaustive documentation of every command, option, flag,
   configuration key and feature, each with a description and a usage
   example for anything non-trivial. For CLIs include exit codes and the
   text of common error messages, since users search for the error they saw.

## Writing rules

- **Present tense, current state only.** Never "we added X", "X is now Y",
  "new in v2", or any before/after framing. Describe the system as if it
  had always been this way. Changelogs exist for history; the README does
  not.
- **Complete for user-facing features.** If a user can invoke it, it is
  documented. Treat each pass as full coverage: check existing entries are
  as complete as the new ones, not just that the new feature got a line.
- **Specific over vague.** Real command names, flag names, paths, defaults
  and outputs. "Configure the timeout" is not documentation; `--timeout MS
  (default 30000)` is.
- **Match the existing tone.** Terse bullets stay terse; prose stays prose.
- **Preserve structure where possible.** Add entries in the logical place;
  only reorganise when the current layout cannot hold the new content.
- **Don't pad.** A simple feature gets one line. Length is not thoroughness.
- **Other docs are in scope.** `--help` strings, docs site pages, man pages,
  and CLAUDE.md or AGENTS.md where they describe user-facing behaviour, all
  drift the same way the README does. Apply the same inventory-and-audit
  pass to each.
