# Urgency Signals — rating a project's demand strength

This rubric produces the **demand strength** rating (HIGH / MEDIUM / LOW) the skill
ranks by. Its core is the **U (Unavoidable)** dimension of
[PULL](pull-framework.md): how hard is it for this person to *postpone* the
project? — amplified by **willingness to pay** (below).

**Demand-only:** rate the strength of the *need*, never the appeal of a solution.
How hard a job would be to serve, or whether it's a good business, is supply
analysis and must not move this rating. Strong demand for a job nobody should build
is still strong demand.

**Grounding rule:** only mark a signal present if the transcript shows it. Cite a
verbatim quote. Absence of a signal is not evidence against demand — it's just
unknown.

## The core principle: weigh actions over feelings

**What someone has already *done* about a problem is far stronger evidence of
urgency than how they *feel* about it right now.** Talk is cheap; spent time,
money, and political capital are not. A calm "we built a tool for this last
quarter" outranks an impassioned "this is absolutely killing us" that is followed
by no action.

So classify on a **hierarchy of evidence**, strongest first:

### Tier 1 — Revealed behaviour (highest priority)

Past, observable actions the person or their org has *already taken* to solve this
problem. These are the signals that should drive a HIGH rating. Look for:

1. **Already built / bought / hired** — they made something, paid for a tool, or
   assigned people to it. ("We built an account research tool", "we bought Clay",
   "we started a sales enablement function this year.")
2. **Money already committed / willingness to pay** — budget approved, a vendor
   already paid for, a workaround already being funded, or an explicit statement of
   what they'd pay to solve it. Money already moving is the single strongest demand
   signal; current spend on the problem is a direct measure of its intensity.
3. **Time already sunk** — meaningful hours already spent, repeatedly, on the
   problem or a workaround. ("I spend all day on this", "days and days trolling
   through reports.")
4. **Rules / decisions already made** — they changed process, banned a tool,
   reorganised a team, set a policy. Action that cost them something to enact.
5. **Repeated or escalated attempts** — they tried option A, it failed, they moved
   to option B. A trail of attempts is a trail of urgency.
6. **A concrete triggering event already happened** — an incident, outage, lost
   deal, failed audit, exposed mistake, or key departure that has *already*
   occurred and forced a response.

The diagnostic question for Tier 1: **"What has this person already done about
this?"** The more they've spent (built, bought, hired, banned, reorganised,
retried), the higher the urgency — regardless of tone.

### Tier 2 — Committed future action with a forcing function

Concrete, externally-anchored pressure that makes deferral costly, even if the
action is still ahead of them:

7. **Hard external deadline** — a date they don't control: compliance/audit
   (SOC2, HIPAA, GDPR), reporting periods (quarter-/year-end, board, earnings),
   contractual dates (renewal, SLA, go-live), seasonal windows, a launch date.
8. **Top-down mandate** — an exec/board is actively requiring it, ideally tied to
   a date, someone's OKRs, or their review. Stronger when the exec is already
   involved (Tier 1), weaker when it's a vague "leadership cares."
9. **On the critical path** — this project is blocking a larger, higher-priority
   initiative that others are already waiting on.

### Tier 3 — Stated intent and feelings (corroborating only)

Present-tense signals. These **support** a rating but should rarely lift a project
to HIGH on their own — they are what people say, not what they've done:

10. **Emotional intensity / frequency** — strong or repeated, unprompted framing
    ("this is killing us", "the team said *stop*", "every single day"). Real
    signal of felt pain, but discount it until you find the Tier-1 action it
    produced.
11. **Stated consequence of inaction** — they can articulate what breaks if it
    slips (vs. no downside named).
12. **Expressed desire / plans** — "we really want to", "we're looking into",
    "at some point we need to". Intent without action sits here, not higher.

## The deferability test

The core U check from PULL: **"Is it acceptable if this person postpones this
project?"** Answer it from their *behaviour*: someone who has already built, paid,
banned, or reorganised has answered "no" with their actions. Someone who only
*says* it's urgent but has done nothing has, in practice, been deferring it.

## Decision guide

**HIGH — Unavoidable now.** Backed by **Tier-1 revealed behaviour**: they have
already spent real time, money, or political capital on it (built/bought/hired/
banned/reorganised/retried), **or** a concrete triggering event has already forced
a response — **and** deferral is clearly not acceptable. A hard external deadline
(Tier 2) also qualifies. Emotional language alone never earns HIGH.

**MEDIUM — Real but deferrable.** Genuine intent and usually some ownership, but
the evidence is mostly Tier 2/3: they *plan* to act, or express strong feeling,
without much observable action yet — and no hard external date or triggering
event. Also lands here when they've taken *some* action but the problem is chronic
and easily deferred.

**LOW — Nice-to-have.** No action taken, no owner, no deadline, no triggering
event — only mild interest or a passing complaint. Easily postponed with no stated
consequence ("someday", "it'd be nice", "just wondering").

## Write-up rules

- In **"Urgency signals observed,"** lead with the Tier-1 behavioural evidence and
  label each signal's tier, so the reader sees the rating is grounded in action,
  not tone. Put emotional/stated signals last.
- If the rating rests on feelings with no observed action, **say so** and lean
  toward MEDIUM/LOW rather than inflating to HIGH.
- When signals conflict, state the tension explicitly (e.g. "loud complaint but no
  action taken → MEDIUM") rather than silently averaging.
