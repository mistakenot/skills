# Strategy: dialectic

Assigned opposing positions. Half the members argue for a proposal, half
against, from the same context. Dialectical inquiry and devil's advocacy
(Mason; Schweiger, Sandberg and Ragan) are the classic structured-conflict
methods, and in group studies they beat consensus discussion on decision
quality.

This strategy breaks the neutral-framing rule on purpose, so it is a second
round, never a first. Assigning a stance narrows what a member will say; you
use it only after `blind-round` or `red-team` has shown you the unforced
distribution. Its job is to get the best possible case for each side, not
to find out what members believe.

## Pairs with

- Prompt: `critique-proposal` for the "against" half, and a mirror of it for
  the "for" half ("What are the strongest reasons this proposal succeeds,
  and what would you strengthen?"). Send the two files as two `ask` runs
  with disjoint `--members`.
- Access: `repo`.
- Members: at least two per side. With five members that is 3/2; alternate
  which side gets three across questions so no provider is always the
  advocate.

## Procedure

```bash
uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file for.md     --members claude,gemini,grok --out "$OUT/for"
uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file against.md --members codex,opencode     --out "$OUT/against"
```

Both runs are blind within their side. Synthesise each side separately per
`synthesis.md`, then write the comparison.

## Aggregation rule

Produce the strongest case for, the strongest case against, and the list of
factual claims the two sides disagree on. Those claims are the things to go
and check. Do not score the debate; a good advocate makes a weak position
sound strong, which is what you asked for.

## Cost note

Two runs, so twice the tokens and wall time of a blind round. Use it for
decisions that are expensive to reverse.
