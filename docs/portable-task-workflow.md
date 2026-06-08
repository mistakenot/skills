---
hash: "54996df5"
id: "230ae987"
read_when: "setting up the task workflow in a new repo, or understanding the end-to-end plan-to-merge lifecycle"
summary: "Self-contained reference for implementing the full AI-agent-driven feature delivery workflow from requirements through merged PR with feedback, designed for reuse across repos."
title: "Portable Task Workflow"
---

# Portable Task Workflow

A complete, repo-agnostic reference for implementing an AI-agent-driven feature delivery workflow: from requirements through merged PR with post-mortem feedback. Designed for Claude Code (or similar coding agents) with skills, worktrees, and tmux-based delegation.

## Overview

```
requirements.md -> solution.md -> context.md -> plan.md -> worktree execution -> PR -> review -> merge -> feedback
```

Planning happens on `main`. Implementation happens on feature branches in isolated git worktrees. Each stage is a discrete skill invoked via slash command. The user reviews and approves between planning stages; execution runs autonomously.

## Prerequisites

- Git repo with `main` branch
- `gh` CLI authenticated (for PR creation, review thread management)
- tmux (for multi-pane delegation, optional)
- Worktree support (git worktrees or equivalent isolation)

## General notes and guidance

- Let's incorporate this advice in to the right planning stages https://raw.githubusercontent.com/multica-ai/andrej-karpathy-skills/refs/heads/main/CLAUDE.md

---

## Stage 1: Planning (on `main`)

### 1.1 Requirements (`/new-task`)

Creates `docs/tasks/$ID-$NAME/requirements.md` from user input.

**Process:**
1. Scan available skills for topic matches (load relevant skills before writing)
2. Read project docs relevant to the domain
3. Create task folder with 3-digit sequential ID
4. Write requirements.md
5. Assume there are latent requirements in the user's head that they haven't communicated in their prompt. Use interactive questions to surface unstated assumptions, clarify ambiguity, and resolve Open Questions with the user, using `AskUserQuestion` tool if Claude.
6. Hard-stop -- user reviews before proceeding

**Requirements template:**

```markdown
# Task $ID: $NAME

## Problem
1-2 sentences describing what's wrong or what's needed.

## Goals
- Bullet list of what this task achieves

## Acceptance Criteria

**AC-1**: $title
- Given: $precondition
- When: $action
- Then: $expected_result

**AC-2**: ...

## Out of Scope
- Product-level boundaries (what this task explicitly does NOT do)

## Open Questions
- [ ] $question (answered: $answer)
```

**Rules:**
- ~1 page max; split larger work into multiple tasks
- ACs use Given/When/Then or casual bullets (match team preference)
- Open Questions must be resolved before moving to solution stage

### 1.2 Solution (`/new-solution`)

Reads approved requirements, explores approaches, writes `solution.md`.

**Process:**
1. Scan available skills for topic matches
2. If straightforward: write solution directly
3. If ambiguous: spawn N parallel subagents to explore options, present pros/cons to user
4. User picks approach
5. Write solution.md
6. Create artifact files if needed (wireframes, architecture diagrams) -- see Artifact Guidelines
7. Validate assumptions -- review every design decision and identify any not clearly dictated by (a) the requirements or (b) pre-established repo patterns. Use interactive questions to double-check those assumptions with the user before presenting the doc. No need to confirm decisions that are obvious from context.
8. Hard-stop -- user reviews

**Solution template:**

```markdown
# Solution: Task $ID

## Approach
1. High-level step
2. High-level step
3. ...

## Files
```
+ path/to/new/file.ts          # brief description
~ path/to/modified/file.ts     # what changes
```

## Test Coverage

| AC  | Test Type   | File                        |
|-----|-------------|-----------------------------|
| AC-1 | e2e        | e2e/tests/feature.spec.ts   |
| AC-2 | integration | src/__specs__/svc.spec.ts   |
| AC-3 | unit       | src/feature.test.ts          |

## Out of Scope
- (copy from requirements + add technical boundaries)

## Rejected Alternatives
- **Option B**: one-line reason it was rejected
- **Option C**: one-line reason it was rejected
```

**Rules:**
- Files section uses `+` for new files, `~` for modified `-` for deletion
- Test Coverage table maps every AC to a test type and file
- Include bare-bones code outlines (types, signatures) in Files section for complex changes

### 1.3 Context + Plan (`/new-plan`)

Reads requirements + solution, gathers codebase context, writes execution plan.

**Context gathering -- 3 parallel subagents:**
- **CB1 (code)**: searches files, functions, types, patterns relevant to the task
- **CB2 (docs)**: searches project documentation for relevant how-tos and concepts
- **CB3 (history)**: searches git commits, past tasks, related work

Each returns findings to the orchestrator who writes `context.md`.

**Context template:**

```markdown
# Context: Task $ID

One sentence describing what this file contains + link to solution.md.

## Key Files
- `path/to/file.ts:42` -- description of relevant code
- `path/to/other.ts:15-30` -- code snippet with explanation

## Patterns
- How similar features are implemented in this codebase
- Relevant conventions and constraints

## Related Tasks
- Task $OTHER_ID: what it did that's relevant here
```

**Context rules:**
- Only facts from codebase: paths, snippets, descriptions
- Full paths relative to repo root
- Every code snippet needs a file path + line reference
- Never paste full files -- excerpts only

**Plan template:**

```markdown
# Plan: Task $ID

## Summary
One sentence describing the implementation approach.

## Changes
| Symbol | File | Description |
|--------|------|-------------|
| + | path/to/new.ts | New service for X |
| ~ | path/to/existing.ts | Add Y method |

## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)

## How to Test
- [ ] `path/to/feature.test.ts` -- unit tests for service
- [ ] `e2e/tests/feature.spec.ts` -- e2e happy path

## Execution Sequence
```
Phase 1 (DB) --> Phase 2 (Backend) --> Phase 4 (E2E)
                                   \-> Phase 3 (Frontend) -/
```

## Plan

### Phase 1: Database Schema
- [ ] Step 1.1: Create migration for new table
- [ ] Step 1.2: Run migration, verify schema
- [ ] Step 1.3: Commit: `feat($ID): phase 1 - database schema`

### Phase 2: Backend Service
- [ ] Step 2.1: Create repository
- [ ] Step 2.2: Create service with business logic
- [ ] Step 2.3: Create server function
- [ ] Step 2.4: Run typecheck
- [ ] Step 2.5: Write and run unit tests
- [ ] Step 2.6: Commit: `feat($ID): phase 2 - backend service`

### Phase 3: Frontend
- [ ] Step 3.1: Create route
- [ ] Step 3.2: Create components
- [ ] Step 3.3: Wire to server function
- [ ] Step 3.4: Run typecheck
- [ ] Step 3.5: Commit: `feat($ID): phase 3 - frontend`

### Phase 4: E2E Tests
- [ ] Step 4.1: Write e2e test covering AC-1 through AC-3
- [ ] Step 4.2: Run e2e tests
- [ ] Step 4.3: Commit: `feat($ID): phase 4 - e2e tests`

## Success Criteria
- [ ] `typecheck` passes
- [ ] All unit tests pass
- [ ] All e2e tests pass
- [ ] Manual verification: $description

## Open Questions
- (empty if all resolved)
```

**Plan rules:**
- Each phase is atomic -- one subagent handles it end-to-end
- Every phase ends with a commit step
- Every phase includes verification (typecheck, tests, lint)
- Execution Sequence shows the dependency DAG for parallel dispatch
- Checkboxes track progress and enable session resumption

### 1.4 Review (`/review-task-docs`)

Optional review stage where a reviewer (human or AI) reads all four docs and leaves inline comments.

**Review checks:**
1. **Requirements**: ACs testable? Features exist? Out-of-scope sensible?
2. **Solution**: File paths exist? Signatures match? Follows project patterns? Security? Test coverage complete?
3. **Context**: Snippets accurate? Line numbers correct? Related files missed?
4. **Plan**: Execution sequence valid? Dependencies correct? Commands correct? Success criteria verify all ACs?
5. **Cross-document**: Every AC -> test coverage -> plan steps? File paths consistent? Approach matches plan steps?

**Comment format (markdown HTML comments):**

```markdown
<!-- UNRESOLVED(P1): Title of issue
REVIEW: Description of the concern with evidence.
-->
```

Priority levels: P1 (blocking), P2 (important), P3 (minor suggestion).

**Resolving comments:**

```markdown
<!-- RESOLVED(P1): Title of issue
REVIEW: Original concern.
AUTHOR: What was changed to address it.
-->
```

**Rejecting comments:**

```markdown
<!-- REJECTED(P1): Title of issue
REVIEW: Original concern.
AUTHOR: Why this doesn't apply, with reference.
-->
```

**Rules:**
- Comments are append-only (track full decision history)
- One thread per issue
- Place comments directly below offending content with blank lines above/below
- Only comment on real issues (structure, security, assumptions), not formatting

### 1.5 Commit Task Docs (`/commit-task`)

Final planning stage. Verifies completeness and commits to `main`.

**Verification checklist:**
- [ ] All 4 files exist: requirements.md, solution.md, context.md, plan.md
- [ ] No unanswered Open Questions
- [ ] All ACs addressed in plan
- [ ] Plan steps are consistent with solution approach
- [ ] Context covers everything plan references

**Commit:**
```bash
git add docs/tasks/$ID-$NAME/*
git commit -m "docs(tasks): add task $ID-$NAME planning docs"
```

**Rules:**
- Do NOT create a feature branch (that happens at execution)
- Do NOT start implementation
- Output: "To execute this task, run: `/execute-task $ID`"

---

## Stage 2: Execution (on feature branch in worktree)

### 2.1 Execute Task (`/execute-task $ID`)

Autonomous end-to-end implementation using the coordinator-subagent pattern.

**Startup sequence:**
1. Find task folder matching ID under `docs/tasks/`
2. Read ALL files: requirements.md, solution.md, context.md, plan.md
3. Verify prerequisites (all docs exist, no open questions, ACs covered)
4. Create isolated worktree with branch name `task/$ID-$NAME`
5. Parse plan.md for phases, steps, execution DAG
6. Find first unchecked phase (supports resumption)

**Coordinator-subagent pattern:**

The coordinator (main session) dispatches one subagent per phase. No nesting beyond two levels.

**What each subagent receives:**
- Absolute worktree path (critical: subagents don't inherit coordinator's cwd)
- Task folder path
- Which phase to execute (by name/number)
- Instruction to read plan.md, context.md, solution.md before starting
- Instruction to identify and use relevant skills before coding
- Instruction to fix routine failures (test bugs, type errors, lint) autonomously
- Instruction to stop on fundamental issues
- Instruction to commit at end: `feat($ID): phase N - description`

**What each subagent returns:**
- Pass/fail status
- Files changed (list of paths)
- Verification results (typecheck, test summaries)
- Issues encountered (even on pass)

**Coordinator responsibilities after each subagent:**
1. Read results
2. Update plan.md checkboxes: `- [ ]` -> `- [x]`
3. Commit: `docs($ID): mark phase N complete`
4. Decide:
   - Clean pass -> dispatch next phase (follow DAG for parallelism)
   - Routine failure subagent couldn't fix -> attempt resolution
   - Fundamental failure -> stop, record what happened, skip to PR
5. Maintain running list of problems encountered

**Parallel vs serial execution:**
- Follow the Execution Sequence DAG from plan.md
- Independent phases can run in parallel when DAG allows
- Core implementation phases -> serial to reduce conflicts
- When in doubt, go serial

**Session resumption:**
If session ends mid-execution, a new session reads plan.md -- checked phases are done, resume from first unchecked phase. No additional state tracking needed.

**Open PR after completion (or after stopping on failure):**

```bash
git push -u origin HEAD
gh pr create --title "feat($ID): $NAME" --body "$(cat <<'EOF'
## Summary
- [1-3 bullets from plan.md summary]

## Phases completed
- [x] Phase 1: name
- [x] Phase 2: name
- [ ] Phase 3: name (failed / skipped)

## Issues encountered
- [Bullet list or "None"]

## How to test
[Copy from plan.md]

## Links
- Task docs: docs/tasks/$ID-$NAME/
- Plan: docs/tasks/$ID-$NAME/plan.md

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 2.2 Delegation (`/delegate-task`)

Dispatch execution to an idle Claude Code pane in a tmux session, keeping the main session free.

**Tmux session structure:** A tmux session (e.g. `project--execute`) with multiple panes, each running a Claude Code instance.

**Idle pane detection criteria (ALL must be true):**
- Running `claude` process
- Ends with empty prompt (no text after prompt marker)
- Status shows `(main)` branch
- No active tool calls, spinners, or "Composing..." indicators
- Not mid-conversation

**Dispatch workflow:**
1. List panes: `tmux list-panes -t $SESSION -F '#{pane_index} #{pane_current_command} #{pane_pid}'`
2. Capture each: `tmux capture-pane -t $SESSION.N -p -S -30 | tail -30`
3. Assess idleness per criteria above
4. Pick best idle pane (lowest context usage, most recently completed work)
5. Send command:
   ```bash
   tmux send-keys -t $SESSION.N '/clear' Enter
   sleep 3
   tmux send-keys -t $SESSION.N '/execute-task $ID' Enter
   ```
6. Wait 10s, capture pane to verify kickoff
7. Report: which pane, confirmation command sent, what pane is currently doing

If no idle panes: report what each pane is doing and stop.

### 2.3 Status Check (`/executor-status-check`)

Monitor all executor panes and report status.

**Status values:**
- **in progress**: agent actively working (text streaming, tool calls)
- **completed**: "Task complete" or PR URL visible with idle prompt
- **stuck**: errors with no recovery, permission prompts, context exhausted (95%+)
- **idle**: empty prompt, no streaming output

**Per-pane extraction:**
- **Task ID**: from `/execute-task NNN`, branch name `task/NNN-`, or file paths `docs/tasks/NNN-`
- **Description**: read first heading from task's plan.md
- **Last message**: summary of last agent output block
- **Suggested next step**: completed+PR open -> `/address-feedback`, feedback resolved -> `/complete-task`, PR merged -> `/clear`

**Output format:**
```
| Pane | Task | Description | Status | Last Message | Next Step |
|------|------|-------------|--------|--------------|-----------|
| 0    | 434  | Add widget  | completed | PR #87 created | /address-feedback |
| 1    | 435  | Fix auth    | in progress | Running e2e tests | -- |
| 2    | --   | --          | idle   | -- | -- |
```

**Probing in-progress agents:** For panes running long or showing unclear progress, use a non-interrupting status check command if the agent supports it.

---

## Stage 3: Review & Feedback (on feature branch)

### 3.1 Address PR Feedback (`/address-feedback`)

Work through all open PR review threads: fix code, reply, resolve.

**Workflow:**

1. **Find PR**: If user specified a PR number/URL, use that. Otherwise detect from current branch:
   ```bash
   gh pr view --json number,title,headRefName,baseRefName
   gh repo view --json nameWithOwner
   ```
   If no open PR on this branch, tell the user and stop.

2. **Fetch unresolved threads**: Use GraphQL to get every unresolved thread with full comment history:
   ```bash
   gh api graphql -f query='
   {
     repository(owner: "$OWNER", name: "$REPO") {
       pullRequest(number: $NUMBER) {
         reviewThreads(first: 50) {
           nodes {
             id
             isResolved
             comments(first: 10) {
               nodes {
                 databaseId
                 body
                 path
                 line
                 author { login }
                 createdAt
               }
             }
           }
         }
       }
     }
   }'
   ```
   Filter to `isResolved: false` only.

3. **Assess each thread**:
   - **Valid, fix needed**: real bug, missing edge case, convention violation, or clear improvement. Fix the code.
   - **Valid, no code change**: question or concern addressed by explanation rather than code change (e.g. "why did you do X?").
   - **Invalid / already addressed**: concern doesn't apply, suggested change would make things worse, or already fixed in a later commit. Still reply explaining why.

4. **Fix code**: read files first, apply minimal targeted edits. After all fixes, run typecheck and relevant tests. Fix any failures before proceeding.

5. **Reply to each thread**: Reply to the **first comment** in each thread using the REST API. Use the `databaseId` of the first comment from step 2.
   ```bash
   gh api repos/$OWNER/$REPO/pulls/$PR/comments/$COMMENT_ID/replies -f body="$REPLY"
   ```
   For fixes: briefly explain what changed and why. For explanation-only: answer directly. For invalid: be respectful, explain concisely.

6. **Resolve each thread**: Use the GraphQL node `id` (e.g. `PRRT_kwDO...`) from step 2, **not** the `databaseId`. Resolve all threads -- including ones where you declined to make a change.
   ```bash
   gh api graphql -f query='
   mutation {
     resolveReviewThread(input: {threadId: "$THREAD_ID"}) {
       thread { isResolved }
     }
   }'
   ```

7. **Push**: `git add -A && git commit -m "address PR feedback" && git push`

8. **Summary**: Report how many threads were processed, which had code fixes vs explanation-only, any threads where you disagreed with the reviewer and why, and whether typecheck/tests passed.

**Rules:**
- Every thread gets a response (don't silently skip)
- Keep replies short (1-3 sentences)
- Skip commit if no code changes were needed

### 3.2 Code Review (`/code-review`)

Structured review of code changes with severity labels.

**Severity levels:** `[blocking]`, `[important]`, `[nit]`, `[suggestion]`, `[praise]`

**Review process:**
1. Read project docs for conventions
2. Read diff, identify intent
3. Identify all touched files
4. Run automated checks (typecheck, tests, lint)
5. Manual review: correctness, security, performance, error handling, testing, architecture
6. Summary with verdict

---

## Stage 4: Completion (on feature branch)

### 4.1 Complete Task (`/complete-task`)

Finalize feature branch and merge to main.

**Prerequisites:** on feature branch (not main), clean working tree, open PR exists.

**Steps:**
1. **Address remaining PR feedback**: check for unresolved threads, invoke `/address-feedback` if any
2. **Run affected tests**: typecheck (always), unit tests (if changed), e2e tests (if frontend/server functions changed)
3. **Push fixes**: if any new commits
4. **Write task feedback**: create `feedback.md` in task folder (see template below)
5. **Tear down worktree environment**: shut down any worktree-local services
6. **Merge PR**: `gh pr merge --squash --delete-branch`
7. **Exit worktree**: switch back to main
8. **Pull latest**: `git pull`
9. **Verify merge**: check log and key files

**Feedback template:**

```markdown
# Feedback: Task $ID

## Problems faced
1. $obstacle -- $context_to_understand

## Reflections
- What was tricky?
- What would you tell yourself at the start?
- What did you almost do but didn't?

## Useful context
- $specific_resource_that_was_valuable
- $architecture_decision_that_helped
```

Commit and push feedback before merging:
```bash
git add docs/tasks/$ID-$NAME/feedback.md
git commit -m "add task feedback for $ID"
git push
```

---

## Stage 5: Learning Loop

### 5.1 Feedback Analysis (`/task-feedback-analyser`)

Extracts recurring patterns from completed task feedback into generalizable workflow rules.

**Process:**
1. Scan `docs/tasks/*/feedback.md` and review comment threads across completed tasks
2. Cluster by theme (e.g., "missing tenant isolation", "stale context references")
3. Filter to themes with 3+ independent examples (different task folders)
4. Draft rules in imperative form with `use_when` guidance and source examples
5. Update project rules file -- merge with existing, assign sequential IDs

**Rule format:**

```markdown
## RULE-$NNN: $imperative_statement

$explanation

**Use when:** $trigger_condition

**Evidence:**
- Task $A: $verbatim_excerpt
- Task $B: $verbatim_excerpt
- Task $C: $verbatim_excerpt
```

**Rules:** 3-example minimum is strict. Never fabricate examples. Track processed files to avoid re-scanning.

---

## Commit Conventions

### Contextual Commits

Commits capture intent and decisions, not just what changed.

**Subject line:** Standard Conventional Commits format: `type(scope): description`

**Body -- action lines (optional, for significant commits):**
```
intent(scope): what user wanted and why
decision(scope): approach chosen when alternatives existed
rejected(scope): what was considered and discarded + reason
constraint(scope): hard limits/dependencies discovered
learned(scope): API quirks, undocumented behaviors
```

**Phase commits during execution:**
```
feat($ID): phase N - $description

intent(task): $what_this_phase_accomplishes
```

**Plan tracking commits:**
```
docs($ID): mark phase N complete
```

---

## Worktree Conventions

- Branch names: `task/$ID-$NAME` (use dashes, never `+` which breaks some review tools)
- Always `git push` to origin before spawning agents with worktree isolation (agent worktrees branch from `origin/main`, not local)
- Subagents spawned inside worktrees do NOT inherit the coordinator's cwd -- always pass absolute paths
- After squash merge, worktree commits are already in main -- discarding is safe

---

## Artifact Guidelines

Artifacts are self-contained `.html` files stored in the task folder (or an `artifacts/` subfolder) and linked from plan.md. They are created during planning -- wireframes and user flow diagrams may appear as early as requirements, technical diagrams and wireframes typically during the solution stage.

### Wireframes

Wireframes are structural layouts, not polished UI. They show where elements go on a page -- buttons, sections, headings -- without real content. Each element should just have a label describing what it is.

**Rules:**
- Self-contained HTML page using the project's CSS framework CDN (e.g. Bootstrap, Tailwind)
- Structural only: grey boxes, placeholder labels, layout grid. No real content or styling beyond framework defaults.
- Match the project's UI framework so wireframes roughly reflect actual component structure
- One wireframe per `.html` file, linked from plan.md

### Diagrams (Mermaid)

Self-contained HTML files that render Mermaid diagrams via [beautiful-mermaid](https://github.com/lukilabs/beautiful-mermaid). Use for flow diagrams, sequence diagrams, ERDs, etc.

**Rules:**
- Use `renderMermaidSVG` from `esm.sh/beautiful-mermaid@1.1.3`
- OK to add short explanation text below the diagram (bullets work well)
- Split any diagram with more than 8 nodes into multiple diagrams
- One diagram per `.html` file, linked from plan.md

**Boilerplate:**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>[Diagram Name]</title>
  </head>
  <body>
    <div id="diagram"></div>
    <ul>
      <li>Brief note about the diagram</li>
    </ul>
    <script type="module">
      import { renderMermaidSVG } from 'https://esm.sh/beautiful-mermaid@1.1.3';

      const svg = await renderMermaidSVG(`graph TD
    A[Start] --> B[Step]
    B --> C[End]`);

      document.getElementById('diagram').innerHTML = svg;
    </script>
  </body>
</html>
```

### When to create artifacts

- **Requirements stage**: user flow diagrams (if the feature involves user-facing flows)
- **Solution stage**: technical diagrams (architecture, sequence), wireframes
- **Solution template**: "Optional: Mermaid diagrams for key flows. Split any diagram > 8 nodes into multiples."

### Linking artifacts

Reference artifacts from plan.md Links section and from the solution.md where relevant:

```markdown
## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)
- [auth-flow.html](./auth-flow.html)
- [settings-wireframe.html](./settings-wireframe.html)
```

---

## File Structure

```
docs/tasks/
  $ID-$NAME/
    requirements.md     # Stage 1.1
    solution.md         # Stage 1.2
    context.md          # Stage 1.3
    plan.md             # Stage 1.3
    artifacts/          # Optional: wireframes, diagrams
      index.html
      flow-diagram.html
    feedback.md         # Stage 4.1 (written at completion)
docs/rules.md           # Stage 5.1 (accumulated workflow rules)
```

---

## Typical Command Sequence

```
/new-task                    # user reviews requirements.md
/new-solution                # user reviews solution.md
/new-plan                    # user reviews context.md + plan.md
/review-task-docs $ID        # optional: AI or human review
/resolve-comments $ID        # address review feedback in docs
/commit-task                 # commit docs to main
/clear
/execute-task $ID            # or: /delegate-task /execute-task $ID
/executor-status-check       # monitor progress (if delegated)
/address-feedback            # fix PR review comments
/complete-task               # merge, feedback, cleanup
```

---

## Adapting to a New Repo

To implement this workflow in another project:

1. **Task folder structure**: Create `docs/tasks/` directory convention
2. **Skills**: Implement each stage as a skill/slash command (or a single orchestrator with stage flags)
3. **CLAUDE.md / agent config**: Add rules for planning on main, worktree isolation, commit conventions
4. **Tmux session**: Set up `$PROJECT--execute` tmux session with Claude Code panes for delegation
5. **GitHub CLI**: Ensure `gh` is authenticated for PR creation and review thread management
6. **Review format**: Adopt the markdown HTML comment format for plan review conversations
7. **Rules file**: Create `docs/rules.md` seeded with project-specific conventions
8. **Feedback loop**: After completing ~10 tasks, run feedback analysis to extract generalizable rules

**Minimum viable version** (no tmux, no delegation):
- `/new-task` + `/new-plan` (combine solution into plan stage)
- `/commit-task`
- `/execute-task` (without subagents -- single agent executes all phases linearly)
- `/complete-task`

Scale up delegation and parallel execution as the team grows.
