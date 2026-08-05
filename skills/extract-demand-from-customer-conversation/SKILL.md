---
name: extract-demand-from-customer-conversation
description: "Extracts customer demand — pull signals, jobs-to-be-done, and unmet needs — from a customer conversation transcript. Use when 'extract demand', 'extract pull', 'analyse customer call', 'what does this customer want', 'mine a customer conversation', or after a sales/support/discovery call. Not for feature brainstorming without a real conversation (use generate-10-ideas)."
---

# Extract Demand From Customer Conversation

Read a customer conversation and extract the distinct **customer projects** in it,
using Rob Snyder's PULL framework. A *project* (PULL's **P**) is a specific,
*product-agnostic* task on the customer's priority list — "organize my sales
data," not "buy a CRM." One conversation usually contains several.

Read [references/pull-framework.md](references/pull-framework.md) for the model
and [references/urgency-signals.md](references/urgency-signals.md) for the demand
rubric before you start.

## Scope: DEMAND only (not supply)

This skill measures **demand** — how badly customers need a job done, what they've
already done about it, and what they'd pay. It does **not** assess solutions.

- **Do NOT** propose product ideas, features, or "what to build"; estimate market
  size or opportunity value; judge feasibility; or decide whether a job is an
  attractive thing to serve. That is separate **supply** analysis, done later.
- **A job can have overwhelming demand and still be a bad thing to build — that is
  fine and out of scope here.** Never let a job's solution-attractiveness (or lack
  of it) raise or lower its demand rating. "They build in-house rather than buy" is
  a valid, real demand signal, not a mark against the job.
- Rank strictly by **strength of demand**, never by how good a business it would be.

## Grounding rule (hard invariant)

**Use ONLY content from the actual transcript / source material. Never elaborate,
infer beyond the text, or invent details, quotes, numbers, or solutions.**

- Every claim must be traceable to the transcript. The in-depth description must
  feature **direct quotes**, copied verbatim.
- If a field can't be filled from the source, write **"Not mentioned in
  transcript"** — do not fill the gap with plausible-sounding content.
- The only place inference is allowed is **Open demand questions** (see below), and
  only as explicitly-labelled questions to validate — never as asserted fact.

This is a *reading* task, not a *writing* task. If it isn't in the source, it
isn't in the output.

## Demand belongs to a person, not a company

PULL is held by an **individual**, not an organisation. Extract each named person's
job(s) first. When several people voice the same job you may present it as one
project, but:

- Keep **each person's evidence separate and labelled** by name.
- **Breadth is not depth.** Three shallow mentions ≠ one strong pull. Rate demand
  strength on the *strongest individual's* evidence, and note how many people
  share the job as a separate breadth signal — never inflate the rating just
  because many people mentioned it.

## Process

1. **Locate the input.** Read the transcript / notes the user points to (a file
   path, pasted text, or a doc). If no input is given, ask for it.

2. **Identify candidate projects per person.** Scan for product-agnostic jobs each
   named person is trying to get done. Split by *job*, not by feature or product.
   Merge restatements of the same job by the same person; separate genuinely
   different jobs. Drop pure commentary with no underlying task.

3. **For each project, fill the demand fields** — strictly from the transcript:
   - **Whose demand** — the named person(s) + role/company. Label evidence by name.
   - **Demand strength** — HIGH / MEDIUM / LOW per
     [references/urgency-signals.md](references/urgency-signals.md). Weigh
     **observable past actions over present feelings**: what has this person
     already *done* about it (built, bought, hired, banned, reorganised, retried,
     paid)? HIGH must rest on that behavioural evidence or a concrete triggering
     event — emotional language alone never earns HIGH.
   - **Urgency / unavoidability signals** (strongest first, tier-labelled) — the
     actions and forcing functions behind the rating.
   - **Willingness to pay / spend** — current spend on the problem or its
     workarounds, budget held, what they said they'd pay, cost of inaction. This is
     demand *intensity* (PULL's "what would you pay me to solve for you?"), not a
     pricing recommendation. "Not mentioned in transcript" if absent.
   - **Alternatives considered (PULL's L — List)** — split into *tried*,
     *considered*, *rejected*, *still using*, each with why. Not just tools named
     in passing — options they actually weighed.
   - **Limitations (PULL's L)** — why those alternatives / the status quo fail to
     get the job done.
   - **In-depth description** — a narrative built from the transcript, weaving in
     **direct quotes**.
   - **Open demand questions** — the unknowns a founder would need to confirm this
     demand is real: e.g. is it truly unavoidable, who holds the budget, what would
     they pay, how many share it. Demand questions only — **not** "what to build".

4. **Rank** projects by **demand strength** (HIGH first). Demand strength ≠ how
   good a business it would be — rank purely on how real and pressing the need is.

5. **Write the report** in the format below. **Unless the user says otherwise,
   write it to a new markdown file in the current working directory** (e.g.
   `demand-<source-slug>.md`) rather than only printing it to the chat. Tell the
   user the path you wrote. (Note: if the CWD is a repo that auto-publishes commits,
   write outside it or warn the user — conversation content may be private.)

## Output format

Save to a `.md` file in the CWD by default. Lead with a ranked summary table, then
one section per project.

**Emit strict, valid CommonMark** so it renders cleanly in any previewer:

- **No raw `<` or `>` characters** in the prose — they get parsed as HTML tags and
  vanish. Never leave angle-bracket placeholders in the output; fill them with real
  content. To show a literal angle bracket, put it in `` `code` ``.
- **Put a blank line between a bold label and the list/paragraph beneath it**, and
  around every heading, table, list, and code block. A list glued directly under a
  `**Label:**` line renders wrong in many parsers.
- **Never start a list item with `[bracketed text]`** — it renders as a broken
  link. Use a bold prefix instead (e.g. `- **Tier 1 (action taken)** — …`).
- Mark inferences with `(inferred)`, not `[inferred]`.
- Keep tables well-formed: a header row, a delimiter row, and the same pipe count
  on every row.

The structure to follow (replace every placeholder with real content):

```markdown
# Demand extracted from SOURCE NAME

| # | Project | Whose | Demand | Shared by |
|---|---------|-------|--------|-----------|
| 1 | one-line job summary | Kelly (Pega) | HIGH | 3 of 6 |
| 2 | one-line job summary | Henry (Cognor) | MEDIUM | 1 |

---

## Project 1 — one-line job summary

**Whose demand:** name(s), role, company

**Demand strength: HIGH** — one-line justification: unavoidability + action taken + WTP

**Urgency / unavoidability signals** (strongest first — actions before feelings):

- **Tier 1 (action taken)** — Kelly: what they did — "verbatim quote"
- **Tier 3 (stated/felt)** — Kelly: what they said — "verbatim quote"

**Willingness to pay / spend:**

- current spend, budget, stated price, or cost of inaction — "verbatim quote"

**Alternatives considered (List):**

- Tried: option — "quote" — why it fell short: reason
- Rejected: option — "quote"
- Still using: option — "quote"

**Limitations:**

- why the alternatives or status quo fail — "verbatim quote"

**In-depth description:**

Narrative built only from the transcript, with direct quotes woven in. No added
interpretation beyond what the customer said.

**Open demand questions:**

- demand-only unknown to validate, e.g. "Who signs off the budget?" (inferred)
```

Repeat the `## Project N` block for each project. Use "Not mentioned in
transcript" for any empty field rather than inventing content.
