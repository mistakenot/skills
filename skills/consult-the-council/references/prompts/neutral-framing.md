# Neutral framing

The council is only worth convening if the members can disagree with you.
Every word you add to the question is a chance to stop that happening.
Language models anchor on presuppositions in a prompt more strongly than
people do: name a preferred option, hint at the answer you expect, or include
your own draft, and most members will elaborate it rather than challenge it.
So the discipline is: fewer instructions, no hints, and put the problem in
front of them rather than your solution.

## Rules

1. **State the situation, then ask one open question.** Context first,
   question last, nothing else. No "I think", no "we're leaning toward", no
   "obviously".
2. **Do not include your hypothesis.** If you have a draft answer, hold it
   back for a second round (`strategies/red-team.md`) after the blind answers
   are in. If members must see it, say only "here is one proposal" and never
   whose it is or how confident you are.
3. **Present options symmetrically or not at all.** "Should we use X?" pulls
   toward X. Either list every option with equal weight and equal detail, or
   list none and ask how they would approach it.
4. **Ask for reasoning, not a verdict.** "How would you approach this and
   why?" produces diverse reasoning. "Which is better?" produces a vote, and
   votes from correlated models are not information.
5. **No role, tone, or format instructions.** "You are a senior architect"
   and "answer in three bullets" both narrow the distribution of answers.
   The strategy file says whether any framing is allowed, and it is minimal.
6. **Do not mention the council.** A member told that four other models are
   answering may hedge toward the consensus it imagines. Each member should
   believe it is the only one asked.
7. **Same text to every member.** Diversity comes from the models, not from
   per-member prompt tweaks. One prompt file, sent verbatim.

## Before and after

Leading:

> We're planning to move the queue from Redis to Postgres because Redis has
> been flaky. Do you agree this is the right call? What should we watch out
> for?

Neutral:

> Context: a job queue currently on Redis, ~2k jobs/min, three consumers,
> occasional lost jobs during failover over the past quarter. Postgres is
> already in the stack. Question: how would you approach making this queue
> reliable, and what would you want to know first?

Leading:

> Review this design and tell me if the caching layer is over-engineered.

Neutral:

> Here is a design (attached). What would you change, and what would you
> keep as is?

## Self-check

Read the prompt file once more and ask: could a member reading this answer
"no, do something else entirely" without contradicting anything I wrote? If
not, the framing is leading.
