---
name: new-task-quick
description: "Plans a task end-to-end in one unattended pass: Requirements, Verification, Solution and Plan tabs, no review stops. Use when 'new task quick', 'quick task', 'plan end-to-end'. Not for stage-by-stage review (use new-task)."
---

# New Task Quick

Run all three planning stages in a single unattended pass, producing the same artifacts as
`/new-task` -> `/new-solution` -> `/new-plan`: a four-tab
`docs/tasks/$ID-$NAME/plan.html` plus `context.md`. Stop once, at the end.

> Part of the planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

Each stage runs the *same* instructions the individual skills run -- they are shared refs, not
copies. This skill supplies the autonomy contract those instructions branch on, and replaces
the three hard-stops with one.

## Autonomy Contract

This is in force for the whole run. The stage refs below carry `When interactive` /
`When running autonomously` forks: **you are running autonomously.**

1. **Do not stop between stages.** No hard-stop, no summary-and-wait, no "shall I continue".
   Finish Stage 3 before you address the user again.
2. **Do not use `AskUserQuestion`.** There is no one to answer.
3. **Never silently guess a load-bearing decision.** Anything you cannot settle from the
   request, the codebase, or a clear repo convention -- and whose answer would change the
   design -- becomes a `<pd-question>`. Then proceed on your own lean. Do not block on it.
4. **Every `<pd-question>` you write MUST carry a non-empty `recommendedAnswer` attribute.**
   Not a prose lean in the question body -- the attribute. The browser pre-fills the answer
   box from it, which is what turns the review into a one-click rubber-stamp; a lean that
   exists only in your chat message is lost the moment the session scrolls away.

   ```html
   <pd-question id="Q-1" status="open" priority="p1" for="<user>"
                title="Durability: JSON file or SQLite?"
                recommendedAnswer="JSON file — no transactions or indexes needed here.">
   ```

   Put the reasoning in the body as usual; put the *decision* in the attribute.
5. **Assumptions you are comfortable proceeding on stay prose bullets.** The rule of thumb in
   [references/tab-requirements.md](references/tab-requirements.md) decides which vehicle:
   if proceeding on your guess would be reasonable, it is a prose assumption; if a wrong
   guess would waste real work, it is a `<pd-question>`.
6. **Keep a running list of every `<pd-question>` you raise**, across all three stages. You
   report it at the end.
7. **Write each tab to `plan.html` before starting the next stage,** so an interrupted run
   leaves usable partial work rather than nothing.

## Stage 1: Requirements

Read [references/stage-requirements.md](references/stage-requirements.md) and follow it.
Produces `docs/tasks/$ID-$NAME/plan.html` with the Requirements tab.

Note the task ID and folder you create -- later stages say "find the active task folder", and
that is this one. Do not re-scan for a different folder.

## Stage 2: Verification + Solution

Read [references/stage-solution.md](references/stage-solution.md) and follow it.
Produces `context.md` and the Verification and Solution tabs.

Its step 1 asks that Open Questions be resolved. Under this contract they are not: questions
you recorded in Stage 1 stay open, carrying their `recommendedAnswer`. Proceed on those leans.

## Stage 3: Plan

Read [references/stage-plan.md](references/stage-plan.md) and follow it.
Produces the Plan tab and backfills `phases`/`tests` onto every `<pd-ac>` card in the
Verification tab.

## Before You Stop

Check your own output, then fix what fails:

- `grep -o '<pd-question[^>]*' plan.html` -- every hit carries a non-empty
  `recommendedAnswer`. Any that doesn't is a question the human has to answer cold; add it.
- Run the pd-lint CLI on `plan.html`. Open questions are expected (that is the gate); any
  *other* issue code is a defect you introduced -- fix it before stopping.

## Hard-stop

Only now, address the user. Present:

1. The path to the finished `plan.html` and a one-paragraph summary of the plan.
2. **Decisions made on your behalf** -- every `<pd-question>` you raised, one line each, as
   `question -> recommendedAnswer`. This is the list the user is being asked to review; make
   it the prominent part of your message, not a footnote.
3. The state of the doc and what to do next: the doc is **blocked** while those questions are
   unanswered -- pd-lint reports `open-question` and `/commit-task` will refuse to
   commit. That is deliberate: it is the gate that stops an unattended plan reaching execution
   on an unmade decision. Tell them to rubber-stamp or override each question, then run
   `/commit-task` followed by `/execute-task`.

If you raised no questions, say so plainly -- the doc is clean and ready to commit.
