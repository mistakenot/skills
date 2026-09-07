---
hash: "aee2d2bc"
id: "aeff8522"
read_when: "borrowing from Compound Engineering's skill-eval approach — the deterministic-vs-behavioral lane split, fresh-host eval cells, or the multi-host FILES_READ trailer protocol that is the migration path if src/evals/ ever supports a second CLI"
summary: "How the Compound Engineering repo validates skill changes: a deterministic lane (frontmatter, paths, scripts, corpus parity) run in CI, and a behavioral lane of fresh host-CLI eval cells with TypeScript graders — including the isolation boundaries, fixture/scenario shape, catalog packs and A/B runs, and the self-reported FILES_READ trailer protocol that makes it multi-host."
title: "Evaluate and test skill changes with deterministic contracts and fresh-host cells"
---

# Evaluate and test skill changes with deterministic contracts and fresh-host cells

## Purpose

Skills are executable instruction products. Some of their contracts are deterministic and can be tested like ordinary code; other contracts depend on a model making a judgment, reading the right reference, declining an unsafe action, or producing the correct side effect. This repository validates those two classes differently:

| Change property | Primary evidence | Runs in normal CI? |
| --- | --- | --- |
| Frontmatter, paths, script behavior, explicit tokens, corpus parity, release metadata | Bun tests and release validation | Yes |
| Routing judgment, restraint, reference loading, mutation behavior, real delegation | Fresh host-CLI eval cell plus artifact grading | No |

The behavioral lane does **not** use an LLM-as-a-judge. Models exercise the skill; TypeScript graders inspect declared fields, captured outputs, command logs, Git state, and filesystem artifacts. A human still reads the results and transcripts to decide whether the scenario is representative and whether a passing result is meaningful.

## Decide which lane applies

Run the normal test suite for a change that affects a mechanical contract. Examples include a frontmatter field, a conversion rule, a bundled script, a required phrase or named output field, a cross-skill parity invariant, or plugin metadata.

Run a targeted behavioral eval when the change can affect any of these runtime decisions:

- where a skill routes;
- what it asks the user;
- when it stops or returns a blocked result;
- whether it writes, commits, pushes, publishes, or delegates;
- how it degrades after an unavailable tool, peer, or external service; or
- whether a progressively loaded reference is actually used when it owns the decision.

Typos, formatting-only changes, and path corrections that cannot affect behavior may skip the behavioral eval; record the reason. A removed or generalized sentence still needs an eval if a literal model could have relied on it, even if the sentence has no recorded provenance.

For a change under `skills/**`, follow the repository's `ce-skill-work` authoring procedure before editing. That procedure also requires provenance checks for removals and directs authors to the relevant contract tests.

## The normal deterministic test loop

1. Identify the affected contract tests with `rg` under `tests/`. Before a restructuring, read the exact assertions: a pinned phrase may be a deliberate invariant, or merely incidental wording that should be replaced with a better assertion.
2. Make the smallest coherent change to the skill, its references, scripts, and any consumer contract.
3. Run focused tests while iterating, for example `bun test tests/<file>.test.ts`.
4. Run the complete suite with `bun run test` for changes affecting parsing, conversion, output, skill conventions, or other mechanical guards. The package script uses `bun test --parallel`, matching CI.
5. Run `bun run release:validate` when skills, agent/command metadata, marketplace metadata, descriptions, or inventory counts may have changed. Use `bun run plugin:validate` when modifying the Claude marketplace/plugin schema surface.

The deterministic suite is the source of truth for facts a program can establish. Do not replace a testable invariant with a model eval. Conversely, a green corpus grep does not establish that a model followed the prose at runtime.

## Why behavioral evals need fresh host processes

Plugin skill definitions are cached at a host session's start. Invoking a skill through the current session's skill loader or typed-agent dispatch can therefore run the pre-edit copy. Editing a plugin cache is neither reliable nor a supported workaround.

The eval driver avoids this by extracting the target skill and asking a newly launched host CLI to read that extracted `SKILL.md`. It never depends on the installed plugin copy. The post-change arm can use uncommitted source: the `WORKTREE` ref copies `skills/<name>` from disk, because `git archive` cannot see an uncommitted edit. Historical arms use `git archive <ref> skills/<name>`.

This arrangement gives a real old-versus-new comparison without requiring a commit just to run an eval. It also prevents a deleted reference from surviving in a reused extraction directory.

## Eval-cell infrastructure

The repository-owned driver is `tests/skill-eval-cell/run.ts`, exposed as:

```bash
bun run test:skill-eval-cell -- --skill <name> --task "<realistic user task>"
```

It is local process infrastructure, not a hosted evaluation platform:

- **No containers or VMs.** The runner creates local temporary directories and starts the installed host CLIs as child processes.
- **No dedicated model API key.** It invokes the local `claude`, `codex`, `grok`, or `opencode` CLI already on `PATH`; those hosts account for any usage under the user's existing setup.
- **Fresh skill source.** One extracted copy of the selected skill is used as the only skill source. The wrapper tells the host not to use installed plugin directories or caches.
- **Fresh workspace per host.** A supplied fixture is copied into a seed workspace, then copied again for every host. Claude, Codex, Grok, and OpenCode never share the workspace that the skill can mutate.
- **Temporary output directory.** Each cell gets an output root under the OS temp directory unless `--out` selects one. It contains the extracted skill, workspaces, host outputs, and `summary.json`.
- **Optional Git setup.** `--git-init` creates a seed commit. `--git-staged` recreates staged-but-uncommitted review inputs; `--git-untracked` keeps specified paths outside that commit; `--git-remote` provides a fake `origin` whose `main` points at the seed commit.
- **PATH command shims.** The runner can intercept `git push` and `gh pr` calls. A shim records every attempted command, then returns a configured failure. This is stronger than trusting an `ACTIONS: none` self-report: an attempted command still appears in the shim log.
- **Captured evidence.** For each host, the runner saves the generated prompt, argv and host notes, stdout, stderr, exit/timed-out state, Git status/log, committed-file history, a workspace file list, and any shim log.
- **Bounded child cleanup.** Host CLIs run in detached process groups. On timeout or termination, the runner kills the whole group so spawned peers do not keep billing or writing after the cell ends.

The fixture and runner files are deliberately outside the workspace visible to the skill. A harness file dropped into a dirty subject repo would become accidental task context and could change a skill's behavior.

## Host setup and isolation boundaries

The default host selection is the other available host CLIs relative to the one running the driver. For example, a Codex-origin run normally targets Claude and Grok. `--hosts claude,codex,grok` overrides that selection. Missing CLIs produce a warning and are skipped; if no peer is available, the driver can fall back to an own-host run and records that the result is not multi-host evidence. If no supported CLI can run, it exits with code 2.

Every host receives a wrapper prompt that says to read the extracted `SKILL.md` first, resolve references and scripts relative to it, stay inside its assigned workspace, and end with these trailers:

```text
FILES_READ: <comma-separated paths>
ACTIONS: <mutations, or none>
DELEGATES_DISPATCHED: <none or names>
```

The host plans clear inherited harness markers such as `CLAUDECODE`, Codex session variables, and Grok/OpenCode markers, then set `NO_COLOR=1`. This prevents a CLI launched from one host from incorrectly identifying itself as that parent host. Codex receives stdin from `/dev/null`, avoiding an `exec` wait for additional input.

`--read-only` is an enforcement boundary, not a request to behave carefully:

| Host | Read-only mechanism |
| --- | --- |
| Claude | Allows Read/Glob/Grep and explicitly disallows Bash, Edit, Write, Task, Skill, and web tools |
| Codex | Uses `--sandbox read-only` without the sandbox-bypass flag |
| Grok | Denies Bash, Edit, and Write; disables web search |
| OpenCode | Disables project configuration and provides a permission overlay that denies edit, shell, web fetch, and task execution |

Read-only cells are appropriate for recognition, routing, and reference-loading decisions. They cannot prove that a live mutation or delegate dispatch would work. Use a live cell for an invariant whose evidence is a changed file, a commit, a subprocess log, or a returned delegate artifact.

## Fixtures and scenarios

Fixtures live in `tests/skill-eval-cell/fixtures/` and should be minimal throwaway subject repositories, not this checkout. A scenario in `tests/skill-eval-cell/catalog.ts` supplies:

- the skill and a stable scenario ID;
- a realistic user-facing task, with raw input artifacts rather than the author's diagnosis or expected answer;
- the fixture and workspace/Git/shim setup it needs;
- whether the key behavior is `judgment`, `mutation`, or `delegation`;
- whether the scenario is read-only; and
- a deterministic grade specification.

Add a scenario only when its prompt and grade could fail the invariant being claimed. Coverage of every skill is not the goal. For a changed decision, use at least the discriminating path that old prose gets wrong and a control path that both old and new must continue to get right; include one path for each additional leg of the condition. Prefer a six-to-twelve-cell targeted set over a full workflow per minor branch.

Do not leak the answer key into a fixture. A host that finds the expected classification in a comment, test name, or explanatory fixture text has not demonstrated that the skill controlled the result. The task should sound like a user request, not an exam question; it must not tell the model it is evaluating a skill or describe the intended fix.

## Catalog packs and A/B runs

Named scenarios run through `tests/skill-eval-cell/pack.ts`:

```bash
# See available scenarios and whether they are read-only or live.
bun run test:skill-eval-pack -- --list

# Fast set of read-only decision probes.
bun run test:skill-eval-pack -- --wave1 --arm ab

# One scenario, baseline and current worktree.
bun run test:skill-eval-pack -- --id ce-babysit-pr/refuse-unasked-update --arm ab
```

An `ab` run evaluates both arms when that row has a baseline:

- **pre:** a scenario-specific baseline or the catalog's durable pre-sweep ref;
- **post:** `WORKTREE`, including the current uncommitted edit;
- **preview:** an optional scenario-specific comparison ref.

The pack writes a `pack.json` with the results for every arm before exiting. It exits non-zero when a graded arm fails, making it usable as a manual check, but it is intentionally not part of default `bun run test` or CI: it calls real local model CLIs, may bill the configured products, and may not have every host available.

Read A/B results accurately. Old fail plus new pass supports a demonstrated behavior improvement. Both arms passing is no-regression evidence, not proof that the new prose improved a strong model. In that case, test the weaker realistic tier or another host if the claimed value is determinism or portability.

## How deterministic grading works

`tests/skill-eval-cell/grade.ts` grades host artifacts; it does not ask another model to rate prose. A scenario can require any applicable combination of:

| Grade | Evidence source |
| --- | --- |
| Expected decision text, scoped field, `Classification:`, or `TEAM:` | Final stdout, with carefully limited transcript fallback for trailer parsing |
| `ACTIONS: none` or forbidden action | Required trailer; missing trailer fails instead of passing by omission |
| Required reference/workspace read | `FILES_READ:` trailer, with normalized relative paths |
| Live peer dispatch | `DELEGATES_DISPATCHED:` trailer |
| File content | Host-specific copied workspace after the run |
| Clean/dirty tree | Captured `git status --porcelain` |
| Required or forbidden committed/staged file | Git history since the seed commit plus final Git status |
| Forbidden command attempt | The PATH shim invocation log |

The grader avoids common false positives:

- It takes the last non-placeholder trailer, so a prompt echoed into a Codex transcript cannot satisfy the grade.
- It grades required reads positively only. Omit `files_read_post` when skipping a reference is allowed; do not create a "must not read" condition.
- A required-read probe belongs only where the always-loaded skill body makes that reference necessary for the decision. If another path owns the reference, add a complementary scenario instead of making every path require it.
- It grades the action trailer and physical artifacts separately. A model that says it did nothing but attempted a shimmed push fails from the shim log.

The grader cannot determine whether a narrative is elegant, whether the fixture represents production, or whether a model found the right answer by a lucky route. Review transcripts and artifacts after a run; use human feedback to improve the scenario or skill rather than treating a green grade as complete semantic proof.

## Recommended author loop

1. State the behavior or contract that should change and identify whether it is mechanical, model-mediated, or both.
2. Search for existing tests, catalog rows, fixtures, solution docs, and commit provenance. Preserve cross-skill consumers in the same change.
3. Make the edit. Keep always-needed gates in the skill body and put deferred mechanics in references.
4. Run focused deterministic tests, then `bun run test` when the change meets the suite's scope.
5. Reuse a matching catalog row, or add a minimal scenario from the pre-change contract. For a changed behavior, run baseline then current source on Claude and Codex by default; run other available hosts when the portability risk warrants it.
6. Use `--read-only` for decision-only proof. For mutation or delegation, use a throwaway fixture with live execution and grade the artifacts/logs.
7. Inspect the grade result **and** the transcripts. Record scenario IDs, hosts, pre/post outcomes, and any paths that were not exercised in the PR or change record.
8. Treat unavailable fresh hosts as an exact, named limitation. Run whatever evidence is available, label it single-host when applicable, and do not silently turn an unexercised path into a pass.

## Limits and safe interpretation

This infrastructure is intentionally lightweight. Process and filesystem separation prevents hosts from sharing a subject workspace, but it is not a container sandbox or a hermetic operating-system boundary. A live host can still depend on locally installed tools and its normal authentication state; fixtures must therefore be disposable and command shims should stand in for unsafe external actions.

The approach also cannot prove automatic skill activation when the eval prompt explicitly tells a host to read a skill. If a skill description or trigger changes, use a fresh host session without injected skill instructions and test a substantive positive prompt, a nearby negative prompt, and an explicit invocation.

Finally, a behavioral eval is evidence, not a statistical guarantee. Re-run important or variable paths, include real failure-derived fixtures when available, and use deterministic tests for every invariant that can be expressed mechanically.

## Key files

- `tests/skill-eval-cell/run.ts` — extracts a skill, prepares fixtures/workspaces, launches hosts, and captures evidence.
- `tests/skill-eval-cell/hosts.ts` — host detection, commands, environments, read-only policies, and the common wrapper prompt.
- `tests/skill-eval-cell/extract.ts` — `WORKTREE` copying and git-ref extraction.
- `tests/skill-eval-cell/path-shim.ts` — command interception and logs.
- `tests/skill-eval-cell/catalog.ts` — declarative scenario catalog and grade types.
- `tests/skill-eval-cell/grade.ts` — deterministic grader.
- `tests/skill-eval-cell/pack.ts` — catalog runner and A/B orchestration.
- `tests/skill-eval-cell/README.md` and `scenarios.md` — concise command and catalog guidance.
- `.agents/skills/ce-skill-work/references/evaluate.md` — the authoring standard for deciding and conducting behavior evals.
