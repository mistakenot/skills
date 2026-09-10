# Strategy: blind-round

One independent round. Every member gets the same prompt, none sees another's
answer, the parent synthesises. This is the default and the purest explore
step: it is the first round of Delphi without the convergence rounds, and
the nominal-group-technique rule of "write silently before anyone speaks".

Use it when you want to know the shape of the answer space before you have
formed a view, or to check a view you are holding back.

## Pairs with

- Prompt templates: `open-question`, `options-symmetric`, `estimate`.
- Access: `repo` when the question is about this codebase; `none` when the
  question is general and repo context would narrow the answers.
- Members: all available.

## Procedure

1. Write the prompt file per `prompts/neutral-framing.md` and the template.
2. Run:

   ```bash
   uv run "$SKILL_DIR/scripts/council.py" ask --prompt-file q.md --out "$OUT"
   ```

   The script preflights the members first and proceeds with whoever passes
   if they make quorum (default 3); under quorum it exits 3 with the fixes.
3. Synthesise per `synthesis.md` before reading `key.json`.
4. Report verbatim answers, clusters, disagreements, minority views, open
   questions, then the key.

## Aggregation rule

Map, do not decide. The output is a set of clusters and the assumptions
that split them. If the parent needs a decision, it makes one after this
step, and says which cluster it chose and why.

## Signs it went wrong

- All answers agree closely: either the question was leading (re-read the
  framing rules), or the answer is genuinely settled and the council was not
  needed.
- One answer is much longer and the others defer to nothing: fine; length is
  not weight.
- A member misread the question: note it, consider whether the framing was
  ambiguous, do not discard it.
