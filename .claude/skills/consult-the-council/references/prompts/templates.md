# Prompt templates

Each template is the whole prompt file. Fill the placeholders and send it
verbatim; do not add preamble, role, or format instructions around it. The
templates are short on purpose (see `neutral-framing.md`): the context block
carries the information, the question carries the ask, and nothing carries
your opinion.

Pick by what kind of answer you need, then check the pairing with the
strategy in `SKILL.md`.

## open-question

For "how should we approach this?" questions with no proposal on the table.

```
Context:
<situation, constraints, and facts a stranger would need. Facts only.>

Question:
How would you approach <the problem>, and what would you want to know first?
```

## options-symmetric

When there are known candidate approaches. Every option gets the same
amount of detail and the same neutral tone; order them alphabetically or
randomly so position does not signal preference.

```
Context:
<situation and constraints>

Candidate approaches (in no particular order):
- <A>: <one neutral sentence>
- <B>: <one neutral sentence>
- <C>: <one neutral sentence>

Question:
How would you choose among these, or something else, for this situation? What
would change your answer?
```

## critique-proposal

For `red-team` and `dialectic`. The proposal is presented as "one proposal",
with no author, no confidence, and no framing of what you hope to hear.

```
Context:
<situation and constraints>

One proposal:
<the proposal, as written, unedited>

Question:
What are the strongest reasons this proposal would fail or underperform, and
what would you do instead?
```

## pre-mortem

Assumes failure and asks for the history. This widens the failure modes
surfaced without steering toward any one of them.

```
Context:
<situation and the plan, as facts>

Assume it is <a year> from now and this has clearly failed.

Question:
Write the most plausible account of what went wrong.
```

## estimate

For sizing, risk, or likelihood questions. Asks for the number and the
reasoning so answers can be compared on their assumptions, not just their
midpoints.

```
Context:
<situation and known facts>

Question:
Estimate <the quantity>, give your range, and state the assumptions your
estimate depends on most.
```

## delphi-round-2

The only template that shows members other answers. Used by
`strategies/delphi.md` after round one. The summary is the synthesis from
`synthesis.md` with labels, not provider names.

```
Context:
<the original context, unchanged>

Question:
<the original question, unchanged>

Summary of independent answers so far:
<clusters of agreement and the disagreements, without attribution>

Given that summary, what is your answer now, and what in the summary did you
find most or least convincing?
```
