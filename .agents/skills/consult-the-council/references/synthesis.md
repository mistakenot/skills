# Synthesis

The answers come back as `A.md`, `B.md`, ... in the output directory with
the provider names withheld in `key.json`. Synthesise before reading the key.
The point of blinding is that "the Claude answer" and "the GLM answer" carry
brand expectations, and those expectations would weight the clustering. Once
the synthesis is written, reveal the key and add attribution as a footnote.

For an explore step the disagreement is the product. Do not average, vote,
or pick a winner unless the strategy says to. Map the space.

## Steps

1. **Read every answer in full** before writing anything. Note, per answer,
   its main recommendation, its key assumption, and anything it raised that
   no other answer did.
2. **Cluster.** Group answers by their core recommendation, not by wording.
   Two answers that reach the same place by different arguments are one
   cluster with two arguments; two that use the same words for different
   plans are two clusters.
3. **Name the disagreements.** For each pair of clusters, state what they
   disagree about and, where visible, which assumption drives the split.
   A disagreement traced to an assumption is a question you can go and
   answer; one that is not is a judgment call to record.
4. **Preserve minority views.** An answer nobody else gave is the one most
   likely to be the thing you had not thought of. It goes in the report even
   if it is wrong, with a sentence on why it might be right.
5. **Collect open questions.** Anything an answer said it would want to know
   first. These are often the most valuable output: they are the facts the
   decision actually turns on.
6. **Reveal the key** (`council.py reveal --out DIR`) and append the mapping.
   If a cluster is one provider alone, say so; if all providers of one
   family agree with each other and nobody else, say that too, since
   correlated errors are the known failure mode of model ensembles.

## Report structure

Use this shape. Keep the verbatim answers attached or linked; a synthesis
the parent cannot audit against the raw answers is a summary, not evidence.

```
## Question
<the prompt, as sent>

## Answers
<A.md .. E.md verbatim, or a link to the output directory>

## Clusters
### <cluster name>: <one-line recommendation>  (answers: A, C)
<the argument(s), the key assumption>

## Disagreements
- <cluster X> vs <cluster Y>: <what they disagree about>; turns on <assumption>

## Minority views
- <label>: <the view and why it might be right>

## Open questions raised
- ...

## Key
A: <provider>, B: <provider>, ...
<notes on family correlation, members that failed and why>
```

## What not to do

- Do not rewrite an answer to make it fit a cluster. Quote it.
- Do not drop an answer because it misunderstood the question. Record that
  it did; a misreading by one model is often a sign the framing was unclear,
  which is information about the prompt.
- Do not conclude "the council recommends X" from an explore strategy. Say
  "three of five converge on X; the split turns on Y".
