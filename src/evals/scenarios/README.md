# Scenarios

A scenario is the task a run measures. The catalog is `ls scenarios/` — there is
no registry file and nothing to update when you add one.

```
scenarios/<name>/
    prompt.md    required   the prompt handed to every arm, verbatim
    setup.sh     optional   prepares the workspace; runs with the workspace as cwd
    fixture/     optional   static files copied into the workspace
```

The shape is `src/assurance/evals/cases/` minus the grader files (`checks.sh`,
`rubric.md`), which this harness does not carry.

Run one with `--scenario <name>` (a bundled name) or `--scenario <path>`.
`--prompt "..."` remains the inline shorthand for a throwaway with no fixture.

## Rules a scenario must follow

**Pin every ref to a literal 40-character sha.** `check_pins` in `scenarios.py`
fails a `setup.sh` that names a branch at a `git checkout`, a `--branch` flag or
an archive URL, and fails one that fetches remote content without a sha
anywhere. A `SHA=...` assignment used as `"$SHA"` is expanded and accepted. This
is enforced rather than reviewed: a floating fixture drifts between runs, and on
a "plan how to add X" task an upstream X merged since the scenario was written
would be handed to the agent as the answer.

**Prefer a tarball to a clone.** `https://codeload.github.com/<owner>/<repo>/tar.gz/<sha>`
fetches the tree without the history. It is much faster, and there is no history
in the result for an agent to mine.

**Never make the workspace root a git repo.** Extract or clone into a
subdirectory. The clean-room canaries reject a cell whose workspace is (or sits
under) a git repo, because Claude Code walks up from cwd and re-discovers a
repo's project context.

**setup.sh must produce a relocatable tree.** It runs once per scenario, in a
cache directory, and the result is copied into each cell's workspace — so the
directory it runs in is not the directory the agent sees. Do not bake absolute
paths into anything it generates.

## The cache

A scenario with a `setup.sh` is prepared once into `cache/<name>-<key>/ws/`, and
every cell is seeded by copying that tree. A four-cell run therefore fetches
once, not four times. The key is a content hash of `setup.sh` plus `fixture/`,
so editing either produces a new entry rather than reusing a stale one; a
`FETCHED` marker beside the payload records when the fetch happened and is never
rewritten on reuse. `cache/` is gitignored and safe to delete.
