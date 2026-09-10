# Strategy: red-team

One blind round using the `critique-proposal` template: members see a
specific proposal and are asked for the strongest reasons it fails and what
they would do instead. This is the exploit-adjacent member of the set: a
proposal exists and you want it attacked, not the space mapped.

Because the proposal is on the table, the leading-the-witness risk is at its
highest. Two rules carry most of the weight:

- Present it as "one proposal", with no author and no confidence. Members
  told it is your plan soften; told it is a draft from elsewhere, they cut.
- Run it after a `blind-round` on the same question, not instead of one, when
  you can afford both. The blind round tells you what members would have
  proposed unprompted; the red team tells you what they think of yours. The
  gap between the two is the finding.

## Pairs with

- Prompt template: `critique-proposal`.
- Access: `repo` when the proposal is about this codebase; members will
  check claims in it against the code, which is exactly what you want.
- Members: all available. Diversity of attack matters here more than
  anywhere; same-family models find the same holes.

## Aggregation rule

Cluster by objection. For each objection record how many members raised it,
whether any member answered it, and whether it is fatal, costly, or
cosmetic in your judgment (say that this is your judgment). Then list the
alternatives members proposed instead, each as its own line, without
picking one.

## Signs it went wrong

- Every member agrees the proposal is fine: the framing leaked approval, or
  the proposal is good. Re-read the prompt for hedges such as "we believe"
  or "carefully designed" before trusting the second explanation.
- Objections are all generic ("consider testing", "monitor performance"):
  the proposal lacked enough detail to attack. Add the specifics and rerun.
