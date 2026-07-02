"""
Tests for the strategy-only blind-differential core (blind_grade.py) and the
blind-mode report renderer (grade_report.render_blind_report).

Covers:
  AC-3: the harness-added scaffolding blind_grade.py injects carries no arm
        labels / scorecards / skill-name framing. Per D-4 the freeform doc body
        is NOT redacted (an organic token is left intact — that's AC-6's job),
        so we assert scaffolding-cleanliness, not body-token-freeness.
  AC-1/AC-4: the rendered report is a winner + prose block with no 0-3 grid.
  Round-trip: unblind maps the judge's A/B verdict back to the right arms.
"""

import os
import sys

# Add the evals/ directory to sys.path so we can import the eval modules.
_EVALS_DIR = os.path.join(os.path.dirname(__file__), "..", "evals")
sys.path.insert(0, os.path.abspath(_EVALS_DIR))

import blind_grade  # noqa: E402 — must follow sys.path manipulation
import grade_report  # noqa: E402

# Token-free strategy bodies so any arm identifier in the assembled judge input
# must have come from the harness scaffolding, not the doc bodies.
_BASELINE_MD = "# Plan\n\nWrite a comprehensive suite covering every component and browser."
_WITHSKILL_MD = "# Plan\n\nProtect the one revenue-bearing flow; skip the volatile copy."


# ---------------------------------------------------------------------------
# Round-trip: anonymise → unblind recovers the real arms (AC-3)
# ---------------------------------------------------------------------------


def test_unblind_round_trips_across_seeds():
    """For every seed, un-blinding maps the judge's A/B verdict to the right arm."""
    for seed in range(12):
        judge_input, mapping = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=seed)

        # Mapping is a bijection over the two real arms.
        assert set(mapping.keys()) == {"A", "B"}
        assert set(mapping.values()) == {"baseline", "withskill"}

        # Build a judge verdict that picks the label holding the withskill arm.
        skill_label = "A" if mapping["A"] == "withskill" else "B"
        other_label = "B" if skill_label == "A" else "A"
        judge_json = {
            "winner": skill_label,
            "verdict": "prose",
            "weaknesses_a": "weakness of A",
            "weaknesses_b": "weakness of B",
            "guess_skill": skill_label,
            "guess_confidence": "high",
        }

        result = blind_grade.unblind(judge_json, mapping)

        assert result["winner"] == "withskill"
        assert result["loser"] == "baseline"
        # The loser's weakness prose is the one keyed to the baseline label.
        assert result["weaknesses_loser"] == judge_json[f"weaknesses_{other_label.lower()}"]
        assert result["guess_skill"] == "withskill"
        assert result["guess_correct"] is True


def test_unblind_handles_baseline_winner_and_wrong_guess():
    """A baseline win + an incorrect skill guess un-blind correctly."""
    _, mapping = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=1)
    baseline_label = "A" if mapping["A"] == "baseline" else "B"
    judge_json = {
        "winner": baseline_label,
        "verdict": "baseline won",
        "weaknesses_a": "wa",
        "weaknesses_b": "wb",
        "guess_skill": baseline_label,  # guesses the baseline is the skill arm → wrong
        "guess_confidence": "low",
    }
    result = blind_grade.unblind(judge_json, mapping)
    assert result["winner"] == "baseline"
    assert result["loser"] == "withskill"
    assert result["guess_skill"] == "baseline"
    assert result["guess_correct"] is False


# ---------------------------------------------------------------------------
# Scaffolding cleanliness: no arm labels / scorecards / skill framing (AC-3)
# ---------------------------------------------------------------------------


def test_judge_input_scaffolding_carries_no_arm_identity():
    """With token-free bodies, the assembled input names only Strategy A / B."""
    for seed in range(6):
        judge_input, _ = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=seed)
        lowered = judge_input.lower()
        for forbidden in ("baseline", "withskill", "with-skill", "assurance-strategist", "scorecard"):
            assert forbidden not in lowered, f"scaffolding leaked '{forbidden}' (seed {seed})"
        assert "Strategy A" in judge_input
        assert "Strategy B" in judge_input


def test_freeform_body_is_not_redacted():
    """D-4: an organic skill-name mention in a doc body is left intact."""
    leaky = "# Plan\n\nFollowing the assurance-strategist methodology, test the CTA."
    judge_input, _ = blind_grade.anonymise(leaky, _WITHSKILL_MD, seed=0)
    # The body token survives (blind_grade does NOT redact freeform content).
    assert "assurance-strategist" in judge_input


# ---------------------------------------------------------------------------
# Leakage probe: unblind maps guess_skill back to the real arm (AC-6)
# ---------------------------------------------------------------------------


def test_unblind_maps_guess_to_real_arm_independent_of_winner():
    """The leakage guess un-blinds to the right arm even when it disagrees with
    the winner — a judge can pick the baseline as better yet still guess the
    withskill arm is the skill arm (a leak worth flagging)."""
    _, mapping = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=3)
    baseline_label = "A" if mapping["A"] == "baseline" else "B"
    skill_label = "A" if mapping["A"] == "withskill" else "B"
    judge_json = {
        "winner": baseline_label,  # judge prefers baseline's strategy
        "verdict": "baseline won on calibration",
        "weaknesses_a": "wa",
        "weaknesses_b": "wb",
        "guess_skill": skill_label,  # but still fingerprints the skill arm
        "guess_confidence": "high",
    }
    result = blind_grade.unblind(judge_json, mapping)
    assert result["winner"] == "baseline"
    assert result["guess_skill"] == "withskill"
    assert result["guess_correct"] is True


# ---------------------------------------------------------------------------
# Graceful degradation: garbled / missing judge JSON → "parse failed" row
# ---------------------------------------------------------------------------


def test_garbled_judge_json_unblinds_to_parse_failed_marker():
    """A garbled judge verdict (no extractable JSON object) degrades to a
    parse-failed marker instead of raising — reusing extract_json_object."""
    garbled = "The judge rambled and never emitted a JSON object at all."
    assert blind_grade.extract_json_object(garbled) is None

    _, mapping = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=0)
    result = blind_grade.unblind(blind_grade.extract_json_object(garbled), mapping)
    assert result["blind_parse_failed"] is True
    assert result["winner"] is None


def test_missing_winner_key_unblinds_to_parse_failed_marker():
    """A JSON object that parses but lacks a winner also degrades gracefully."""
    _, mapping = blind_grade.anonymise(_BASELINE_MD, _WITHSKILL_MD, seed=0)
    result = blind_grade.unblind({"verdict": "no winner field"}, mapping)
    assert result["blind_parse_failed"] is True


def test_blind_report_renders_parse_failed_row(tmp_path):
    """The report renderer shows a 'parse failed' row with the raw judge text."""
    grader_data = {
        "blind_parse_failed": True,
        "winner": None,
        "mapping": {"A": "baseline", "B": "withskill"},
        "raw_judge": "not json at all",
    }
    report = grade_report.render_blind_report(tmp_path, grader_data, case="strategy/x")
    assert "parse failed" in report.lower()
    assert "not json at all" in report
    # No fabricated winner or dimension grid on a failed parse.
    assert "**Winner**: withskill" not in report
    assert "Dimension" not in report


# ---------------------------------------------------------------------------
# Report shape: winner + prose, no dimension grid (AC-1 / AC-4)
# ---------------------------------------------------------------------------


def test_blind_report_is_winner_plus_prose_no_dimension_grid(tmp_path):
    grader_data = {
        "winner": "withskill",
        "loser": "baseline",
        "verdict": "The winner right-sizes testing to a low-stakes surface.",
        "weaknesses_winner": "Could name a rollback signal.",
        "weaknesses_loser": "Over-invests in snapshotting volatile marketing copy.",
        "guess_skill": "withskill",
        "guess_confidence": "medium",
        "guess_correct": True,
        "mapping": {"A": "baseline", "B": "withskill"},
    }
    report = grade_report.render_blind_report(tmp_path, grader_data, case="strategy/x")

    # Winner + prose diagnosis are present.
    assert "**Winner**: withskill" in report
    assert "right-sizes testing" in report
    assert "Over-invests in snapshotting" in report
    assert "guess" in report.lower()

    # No decomposed 0-3 dimension grid and no answer key.
    assert "Dimension" not in report
    assert "| Baseline | With-skill |" not in report
    assert "0-3" not in report
    assert "answer key" not in report.lower()
