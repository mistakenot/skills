---
name: postmortum
description: "Write detailed technical postmortem reports for recent issues or problems, preserving enough evidence for an engineer to trace the source issue and recreate it. Use when 'postmortum', 'postmortem', 'incident report', 'write up this issue', 'document this outage', 'root cause writeup', or when the user wants a committed markdown report under docs/postmortums with structured front matter including status and description."
---

# Postmortum

Write a detailed technical postmortum for a recent issue or problem. The report is an investigation artifact for a later engineer who needs to understand, reproduce, and fix the issue.

## Workflow

### 1. Identify the source issue

Use the user's description as the starting point. If the issue is ambiguous, inspect local evidence before asking follow-up questions:

- Git history, branch name, diffs, issue IDs, PRs, commit messages, and recent logs.
- Test failures, CI output, runtime errors, reproduction commands, screenshots, stack traces, and user reports.
- Relevant code paths, configuration, data migrations, dependency changes, feature flags, and environment details.

Ask the user only when the report cannot be made traceable without information that is not present locally.

### 2. Gather evidence

Collect enough concrete evidence that another engineer can trace the issue back to its source. Prefer primary artifacts over summaries.

Record:

- Exact commands run and important outputs.
- File paths, symbols, commits, branches, PRs, issues, logs, timestamps, and environment values.
- Observed behavior, expected behavior, error messages, and conditions required to trigger the issue.
- What was checked and ruled out.
- Confidence level for root-cause claims.

Do not invent missing details. Mark unknowns explicitly.

### 3. Create the report file

Create `docs/postmortums/` if it does not exist. Write the report to:

```text
docs/postmortums/$DATE-$slug.md
```

Use the current local date for `$DATE` in `YYYY-MM-DD` format. Generate `$slug` from the issue title or symptom in lowercase kebab-case.

### 4. Required front matter

Every report must start with YAML front matter. Include `status` and `description` exactly as required fields.

```yaml
---
title: "Short technical title"
description: "One-sentence description of the problem and affected behavior."
status: "ready-for-fix"
date: "YYYY-MM-DD"
slug: "kebab-case-slug"
severity: "unknown"
impact: "Brief impact statement"
source_issue:
  type: "user-report | github-issue | pull-request | ci-failure | incident | other"
  id: null
  url: null
  reported_at: null
environment:
  repo: "owner/name or local path"
  branch: "current branch"
  commit: "current commit SHA"
tags: []
---
```

Use `status: "draft"` when evidence is incomplete or important reproduction details are missing. Use `status: "ready-for-fix"` when the report is sufficiently complete for an engineer to start remediation. Use another clear lowercase status only when the user or repo conventions require it.

### 5. Report structure

Use this structure unless the repo has a stronger local convention:

```markdown
# [Title]

## Executive Summary

Briefly state what failed, who or what was affected, current status, and the most likely root cause.

## Source Issue Trace

Link or describe the original report, issue, PR, CI run, chat message, commit range, or observed failure. Include enough identifiers to find it again.

## Impact

Describe user-visible, operational, data, security, performance, or developer impact. State unknowns explicitly.

## Timeline

List relevant events with timestamps when available. Include detection, reproduction, investigation milestones, and any mitigations.

## Technical Context

Explain the relevant system behavior, code paths, dependencies, config, data shape, and assumptions needed to understand the issue.

## Symptoms and Evidence

Document exact errors, logs, screenshots, command output summaries, failing tests, affected files, and observed behavior.

## Reproduction

Provide step-by-step reproduction instructions with prerequisites, commands, inputs, expected failure, and cleanup. If full reproduction is impossible, provide the closest partial reproduction and explain the missing dependency.

## Root Cause Analysis

Explain the likely root cause and causal chain. Distinguish confirmed facts from hypotheses, and cite the evidence for each claim.

## What Was Ruled Out

List plausible causes investigated and why each is unlikely.

## Remediation Guidance

Describe the recommended fix direction, files likely to change, tests to add or update, migration or rollout concerns, and any risks.

## Open Questions

List unresolved questions blocking a confident fix or verification.

## Appendix

Include raw command outputs, links, diffs, stack traces, logs, or extra notes that would help recreate the issue without redoing the investigation.
```

### 6. Verify and commit

After writing the report:

1. Re-read the file and verify the front matter is valid YAML and includes `description` and `status`.
2. Verify the report includes enough source trace and reproduction detail for a later engineer to act.
3. Stage only the new report file.
4. Commit that file to the current branch.

Use a commit message like:

```text
Add postmortum for $slug
```

Do not stage unrelated work. If unrelated changes are already present in the working tree, leave them untouched and commit only `docs/postmortums/$DATE-$slug.md`.

## Output

Tell the user the report path, the commit hash, the status value used, and any major unknowns that remain.
