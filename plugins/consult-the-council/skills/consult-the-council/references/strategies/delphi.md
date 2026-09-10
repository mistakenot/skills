# Strategy: delphi

Rounds. Round one is a `blind-round`; the parent synthesises it without
attribution; round two sends the original question plus that synthesis back
to the same members and asks what they think now. Repeat until answers stop
moving, usually two or three rounds. This is the RAND Delphi method:
anonymous, iterative, with controlled feedback.

Delphi converges. That makes it the exploit member of this set: use it when
you need the council to reach a position, not when you want to see the
spread. If you only want the spread, stop after round one; that is
`blind-round.md`.

The anonymity matters. Members see a summary of clusters, never "Claude
said". A synthesis that leaks provider identity or the parent's preference
turns Delphi into a persuasion exercise.

## Pairs with

- Prompt: any first-round template for round one, `delphi-round-2` for the
  later rounds.
- Access: `repo`, unchanged between rounds.
- Members: all available, the same set every round.

## Procedure

```bash
uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file q.md --out "$OUT/r1"
# synthesise r1 per synthesis.md (blind), write the cluster summary into q2.md
uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file q2.md --out "$OUT/r2"
```

Between rounds, put only the cluster summary and disagreements into the
round-two prompt. Not the verbatim answers, not the key, not your view.

Stop when a round produces no new clusters and no member changes cluster,
or after three rounds. Answers that keep moving after three rounds are
telling you the question is underdetermined; record that as the result.

## Aggregation rule

Report the final-round clusters with counts, the movement between rounds
(who changed and what they said persuaded them), and the residual
disagreement. The movement is the useful part: an argument that moved two
members is stronger evidence than a position three members started with.

## Cost note

N rounds is N times the cost of a blind round, plus the parent's synthesis
each time. Budget for two rounds; a third is rarely worth it.
