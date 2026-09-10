# Strategy: pre-mortem

One blind round using the `pre-mortem` template: members are told the plan
has already failed and asked to write the history. Gary Klein's technique;
the reframing from "what might go wrong?" to "what did go wrong?" reliably
produces more, and more specific, failure modes, because members stop
evaluating the plan and start explaining an outcome.

Use it once a plan exists and before it is committed to. It does not need
the plan to be good; it needs the plan to be stated.

## Pairs with

- Prompt template: `pre-mortem` only.
- Access: `repo` if the plan touches this codebase (members can check whether
  the failure they imagine is actually possible here).
- Members: all available.

## Procedure

Same as `blind-round.md`, with the `pre-mortem` template. State the plan as
facts, not as a proposal you are attached to: "the plan is to X" not "we
think X is the right approach".

## Aggregation rule

Cluster by failure mode, not by recommendation. For each cluster record how
many members raised it and whether it is a risk the plan already mitigates.
The report's most useful section is the failure modes raised by exactly one
member; those are the ones the plan's authors did not see either.

Do not rank by likelihood. Members' likelihood judgments are the least
independent part of their answers; the existence of a failure mode is the
signal.

## Follow-up

A pre-mortem naturally feeds a `red-team.md` round: take the top failure
modes, revise the plan, and send the revision for critique.
