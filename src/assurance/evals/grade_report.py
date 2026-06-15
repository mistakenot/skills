#!/usr/bin/env python3
"""
Assurance eval report generator.

Reads both arms' out.json, scorecards, and grader JSON from a run directory,
then writes report.md with mechanical + grader scores side by side.

Usage: grade_report.py <run-dir>

The run-dir must contain:
  baseline/out.json, baseline/scorecard.json
  withskill/out.json, withskill/scorecard.json
  grader.json

Stdlib-only — run via: uv run --no-dev python grade_report.py <run-dir>
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_json_object(text: str) -> dict | None:
    """Defensively extract the first balanced JSON object from text.

    Handles:
    - Clean JSON
    - JSON wrapped in ```json ... ``` fences
    - JSON preceded/followed by commentary
    Returns None if no valid JSON object can be extracted.
    """
    # Strip markdown code fences
    stripped = re.sub(r"```(?:json)?\s*\n?", "", text)
    stripped = re.sub(r"\n?```", "", stripped)

    # Find the first { and try to extract a balanced object
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


def read_json_file(path: Path) -> dict | None:
    """Read and parse a JSON file, returning None on failure."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_skill_version() -> str:
    """Get the short git hash for skill version."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def render_report(run_dir: Path, case: str = "") -> str:
    """Render the full report.md content from a run directory."""
    # Read arm outputs
    baseline_out = read_json_file(run_dir / "baseline" / "out.json")
    withskill_out = read_json_file(run_dir / "withskill" / "out.json")

    # Read scorecards
    baseline_sc = read_json_file(run_dir / "baseline" / "scorecard.json")
    withskill_sc = read_json_file(run_dir / "withskill" / "scorecard.json")

    # Read grader output
    grader_raw = None
    grader_path = run_dir / "grader.json"
    if grader_path.exists():
        grader_raw = grader_path.read_text()

    # Parse grader JSON defensively
    grader_data = None
    grader_parse_failed = False
    if grader_raw:
        # Try parsing the raw file as JSON first (it might be a clean claude -p envelope)
        try:
            envelope = json.loads(grader_raw)
            # If it's a claude -p envelope, extract .result
            if isinstance(envelope, dict) and "result" in envelope:
                grader_data = extract_json_object(envelope["result"])
            else:
                # It might be the grader scores directly
                grader_data = envelope
        except json.JSONDecodeError:
            grader_data = extract_json_object(grader_raw)

        if grader_data is None:
            grader_parse_failed = True

    # Header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    model = os.environ.get("MODEL", "claude-sonnet-4-20250514")
    skill_version = get_skill_version()

    lines = [
        "# Eval Report",
        "",
        f"- **Case**: {case or run_dir.name}",
        f"- **Model**: {model}",
        f"- **Skill version**: {skill_version}",
        f"- **Timestamp**: {timestamp}",
        "",
    ]

    # Cost summary (if available)
    for arm_name, arm_out in [("baseline", baseline_out), ("withskill", withskill_out)]:
        if arm_out and "total_cost_usd" in arm_out:
            lines.append(f"- **{arm_name} cost**: ${arm_out['total_cost_usd']:.4f}")
    lines.append("")

    # Mechanical scorecard table
    lines.append("## Mechanical Scorecard")
    lines.append("")
    lines.append("| Check | Baseline | With-skill |")
    lines.append("|-------|----------|------------|")

    t1_checks = ["t1_testing_doc", "t1_verify_entry", "t1_tests_dir"]
    t1_labels = {
        "t1_testing_doc": "Testing doc",
        "t1_verify_entry": "Verify entry point",
        "t1_tests_dir": "Tests directory",
    }

    for check in t1_checks:
        b_val = baseline_sc.get(check, "?") if baseline_sc else "?"
        w_val = withskill_sc.get(check, "?") if withskill_sc else "?"
        label = t1_labels.get(check, check)
        lines.append(f"| {label} | {b_val} | {w_val} |")

    # T2 row
    b_cmd = baseline_sc.get("t2_command", "?") if baseline_sc else "?"
    b_status = baseline_sc.get("t2_status", "?") if baseline_sc else "?"
    b_exit = baseline_sc.get("t2_exit", "?") if baseline_sc else "?"
    w_cmd = withskill_sc.get("t2_command", "?") if withskill_sc else "?"
    w_status = withskill_sc.get("t2_status", "?") if withskill_sc else "?"
    w_exit = withskill_sc.get("t2_exit", "?") if withskill_sc else "?"

    b_t2 = f"{b_cmd} ({b_status}, exit {b_exit})" if b_status != "absent" else f"absent"
    w_t2 = f"{w_cmd} ({w_status}, exit {w_exit})" if w_status != "absent" else f"absent"
    lines.append(f"| Test command (T2) | {b_t2} | {w_t2} |")
    lines.append("")

    # Grader score table
    lines.append("## Grader Scores")
    lines.append("")

    if grader_parse_failed:
        lines.append("**grader: parse failed**")
        lines.append("")
        lines.append("Raw grader output:")
        lines.append("")
        lines.append("```")
        lines.append(grader_raw.strip() if grader_raw else "(empty)")
        lines.append("```")
        lines.append("")
    elif grader_data:
        dimensions = ["tests_present", "verify_command", "test_quality", "evidence"]
        dim_labels = {
            "tests_present": "Tests present",
            "verify_command": "Verify command",
            "test_quality": "Test quality",
            "evidence": "Evidence of verification",
        }
        lines.append("| Dimension | Baseline | With-skill |")
        lines.append("|-----------|----------|------------|")

        b_grader = grader_data.get("baseline", {})
        w_grader = grader_data.get("withskill", {})

        for dim in dimensions:
            b_score = b_grader.get(dim, "?")
            w_score = w_grader.get(dim, "?")
            label = dim_labels.get(dim, dim)
            lines.append(f"| {label} | {b_score} | {w_score} |")
        lines.append("")
    else:
        lines.append("(no grader data available)")
        lines.append("")

    # Human verdict section
    lines.append("## Human verdict")
    lines.append("")
    lines.append("<!-- Write your assessment here after reviewing the run artifacts. -->")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print("Usage: grade_report.py <run-dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.is_dir():
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    case = os.environ.get("CASE", "")
    report = render_report(run_dir, case=case)
    report_path = run_dir / "report.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
