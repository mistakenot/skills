#!/usr/bin/env python3
"""
Blind A/B core for the strategy-only assurance eval.

Two arms each produce a testing-strategy markdown doc. This module blinds them
for the judge and un-blinds the judge's verdict:

  anonymise(baseline_md, withskill_md, seed) -> (judge_input, mapping)
      Deterministically (seeded) decides the A/B order and labels the two docs
      only as "Strategy A" / "Strategy B". The harness-added scaffolding carries
      NO arm labels, NO scorecards, and NO with-skill/baseline/skill-name
      framing (AC-3). Per D-4 the freeform doc *body* is inserted verbatim — an
      organic skill-name mention inside a doc is left intact (that leakage is
      the AC-6 probe's job, not this function's). `mapping` records which
      physical arm ("baseline"/"withskill") became "A" vs "B", kept out-of-band.

  unblind(judge_json, mapping) -> result
      Maps the judge's A/B `winner` and `guess_skill` back to real arm names.

Pure/stdlib only. A thin CLI (`anonymise` / `unblind`) lets run.sh wire the
stub and live grader paths through the same code the unit tests exercise.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

# The only harness-added text wrapped around the two docs. It deliberately holds
# no arm identity — just neutral A/B labels — so the judge cannot infer origin
# from scaffolding (AC-3, D-4).
_DOC_HEADER = "## Strategy {label}\n\n"
_DOC_SEPARATOR = "\n\n---\n\n"


def extract_json_object(text: str) -> dict | None:
    """Defensively extract the first balanced JSON object from text.

    Mirrors grade_report.extract_json_object: handles clean JSON, ```json
    fences, and JSON surrounded by commentary. Returns None on failure.
    """
    stripped = re.sub(r"```(?:json)?\s*\n?", "", text)
    stripped = re.sub(r"\n?```", "", stripped)

    start = stripped.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(stripped)):
        c = stripped[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def anonymise(baseline_md: str, withskill_md: str, seed: int = 0) -> tuple[str, dict]:
    """Blind the two arms into a single "Strategy A / Strategy B" judge input.

    Positional inputs are the two physical arms' strategy docs. A seeded coin
    flip decides whether baseline becomes "A" or "B" (order-randomisation), so
    the judge cannot infer origin from position across a run series.

    Returns (judge_input, mapping) where mapping is {"A": <arm>, "B": <arm>}.
    """
    rng = random.Random(seed)
    baseline_is_a = rng.random() < 0.5

    if baseline_is_a:
        mapping = {"A": "baseline", "B": "withskill"}
        doc_a, doc_b = baseline_md, withskill_md
    else:
        mapping = {"A": "withskill", "B": "baseline"}
        doc_a, doc_b = withskill_md, baseline_md

    judge_input = (
        _DOC_HEADER.format(label="A")
        + doc_a.strip()
        + _DOC_SEPARATOR
        + _DOC_HEADER.format(label="B")
        + doc_b.strip()
        + "\n"
    )
    return judge_input, mapping


def unblind(judge_json: dict, mapping: dict) -> dict:
    """Map the judge's A/B verdict back to real arm names.

    Produces a self-contained result the report renderer can consume without
    knowing the blinding: winner/loser arms, verdict + prose weakness of the
    weaker arm, and the un-blinded leakage guess (with correctness).
    """
    winner_label = judge_json.get("winner")
    winner_arm = mapping.get(winner_label)
    loser_arm = _other_arm(mapping, winner_arm)

    weak_by_label = {
        "A": judge_json.get("weaknesses_a", ""),
        "B": judge_json.get("weaknesses_b", ""),
    }
    weak_by_arm = {mapping.get("A"): weak_by_label["A"], mapping.get("B"): weak_by_label["B"]}

    guess_label = judge_json.get("guess_skill")
    guess_arm = mapping.get(guess_label)

    return {
        "winner": winner_arm,
        "loser": loser_arm,
        "verdict": judge_json.get("verdict", ""),
        "weaknesses_winner": weak_by_arm.get(winner_arm, ""),
        "weaknesses_loser": weak_by_arm.get(loser_arm, ""),
        "guess_skill": guess_arm,
        "guess_confidence": judge_json.get("guess_confidence", ""),
        "guess_correct": guess_arm == "withskill",
        "mapping": mapping,
    }


def _other_arm(mapping: dict, arm: str | None) -> str | None:
    """Return the arm in the mapping that is not `arm`."""
    arms = [mapping.get("A"), mapping.get("B")]
    for a in arms:
        if a != arm:
            return a
    return None


# ── CLI ──────────────────────────────────────────────────────────────────────


def _cmd_anonymise(args: argparse.Namespace) -> None:
    baseline_md = Path(args.baseline).read_text()
    withskill_md = Path(args.withskill).read_text()
    judge_input, mapping = anonymise(baseline_md, withskill_md, seed=args.seed)
    Path(args.out_input).write_text(judge_input)
    Path(args.out_mapping).write_text(json.dumps(mapping, indent=2) + "\n")


def _cmd_unblind(args: argparse.Namespace) -> None:
    raw = Path(args.judge).read_text()
    judge_json = extract_json_object(raw)
    if judge_json is None:
        print(f"Error: could not parse judge JSON from {args.judge}", file=sys.stderr)
        sys.exit(1)
    mapping = json.loads(Path(args.mapping).read_text())
    result = unblind(judge_json, mapping)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind A/B grading core.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_anon = sub.add_parser("anonymise", help="Blind two arms into a judge input.")
    p_anon.add_argument("--baseline", required=True)
    p_anon.add_argument("--withskill", required=True)
    p_anon.add_argument("--seed", type=int, default=0)
    p_anon.add_argument("--out-input", required=True)
    p_anon.add_argument("--out-mapping", required=True)
    p_anon.set_defaults(func=_cmd_anonymise)

    p_unblind = sub.add_parser("unblind", help="Un-blind a judge verdict.")
    p_unblind.add_argument("--judge", required=True)
    p_unblind.add_argument("--mapping", required=True)
    p_unblind.add_argument("--out", required=True)
    p_unblind.set_defaults(func=_cmd_unblind)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
