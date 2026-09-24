"""Axial coding: a failure-mode taxonomy, per-plan labels, and the version report.

Open coding leaves free-text notes (notes.py). Axial coding groups them into a
small set of named failure modes and then records, for each reviewed plan,
whether each mode is present. Those labels are what make two skill versions
comparable: "mode X appeared in 4/6 plans at skills A and 1/6 at skills B".

  data/taxonomy.json   the current failure modes, versioned. Hand-edited (by
                       the agent, with the reviewer) — see the skill's
                       axial-coding reference. Shape:
                         {"version": 2, "modes": [{"id": "vague-verification",
                          "name": "...", "definition": "...",
                          "include": "...", "exclude": "..."}]}
  data/labels.jsonl    append-only; one line per judgement:
                         {plan_id, mode, present, taxonomy_version,
                          evidence: [note ids], reason, ts, by}
                       Latest line wins per (plan, mode) within a taxonomy
                       version. Labels from an older version are kept but not
                       counted: a mode whose definition changed is a different
                       question.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

_MODE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class CodingError(ValueError):
    """A taxonomy or label that cannot be used."""


def load_taxonomy(data_dir: Path) -> dict | None:
    path = data_dir / "taxonomy.json"
    if not path.is_file():
        return None
    try:
        tax = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CodingError(f"{path}: {exc}") from exc
    if not isinstance(tax.get("version"), int) or tax["version"] < 1:
        raise CodingError(f"{path}: version must be a positive integer")
    modes = tax.get("modes")
    if not isinstance(modes, list) or not modes:
        raise CodingError(f"{path}: modes must be a non-empty list")
    seen: set[str] = set()
    for m in modes:
        mid = m.get("id") if isinstance(m, dict) else None
        if not isinstance(mid, str) or not _MODE_ID.fullmatch(mid):
            raise CodingError(f"{path}: mode id {mid!r} must be kebab-case")
        if mid in seen:
            raise CodingError(f"{path}: duplicate mode id {mid!r}")
        seen.add(mid)
        for key in ("name", "definition"):
            if not isinstance(m.get(key), str) or not m[key].strip():
                raise CodingError(f"{path}: mode {mid!r} needs a {key}")
    return tax


def make_label(plan_id: str, mode: str, present: bool, taxonomy: dict, plan_ids: set[str],
               by: str, evidence: list[str] | None = None, reason: str = "") -> dict:
    if plan_id not in plan_ids:
        raise CodingError(f"unknown plan {plan_id!r}")
    modes = {m["id"] for m in taxonomy["modes"]}
    if mode not in modes:
        raise CodingError(f"unknown mode {mode!r} (taxonomy v{taxonomy['version']}: {', '.join(sorted(modes))})")
    return {
        "plan_id": plan_id,
        "mode": mode,
        "present": bool(present),
        "taxonomy_version": taxonomy["version"],
        "evidence": list(evidence or []),
        "reason": reason,
        "ts": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "by": by,
    }


def append_label(label: dict, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / "labels.jsonl").open("a") as f:
        f.write(json.dumps(label) + "\n")


def load_labels(data_dir: Path) -> list[dict]:
    path = data_dir / "labels.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def current_labels(labels: list[dict], version: int) -> dict[tuple[str, str], bool]:
    """(plan_id, mode) -> present, latest wins, current taxonomy version only."""
    out: dict[tuple[str, str], bool] = {}
    for lab in labels:
        if lab.get("taxonomy_version") == version:
            out[(lab["plan_id"], lab["mode"])] = bool(lab["present"])
    return out


def version_key(entry: dict) -> str:
    sha = entry.get("skills_sha")
    return f"skills@{sha[:12]}" if sha else (entry.get("arm_id") or "?")


def report(plans: dict[str, dict], verdicts: dict[str, dict], taxonomy: dict | None,
           labels: list[dict], by: str = "version") -> dict:
    """Counts per group (skills version, or fixture) — the numbers an iteration is judged on.

    For each group: plans generated, plans with a verdict and their split, and
    per failure mode how many *labelled* plans have it. A plan counts toward a
    mode only once it has a label for that mode; unlabelled is not "absent".
    """
    keyf = version_key if by == "version" else (lambda e: e.get("fixture_id") or "?")
    cur = current_labels(labels, taxonomy["version"]) if taxonomy else {}
    modes = [m["id"] for m in taxonomy["modes"]] if taxonomy else []
    groups: dict[str, dict] = {}
    for pid, e in sorted(plans.items(), key=lambda kv: (kv[1].get("ingested_at") or "", kv[0])):
        g = groups.setdefault(keyf(e), {
            "plans": 0, "reviewed": 0, "pass": 0, "fail": 0, "defer": 0,
            "modes": {m: {"present": 0, "labelled": 0} for m in modes},
            "fixtures": set(),
        })
        g["plans"] += 1
        g["fixtures"].add(e.get("fixture_id"))
        v = verdicts.get(pid)
        if v:
            g["reviewed"] += 1
            g[v["verdict"]] += 1
        for m in modes:
            if (pid, m) in cur:
                g["modes"][m]["labelled"] += 1
                g["modes"][m]["present"] += int(cur[(pid, m)])
    for g in groups.values():
        g["fixtures"] = sorted(f for f in g["fixtures"] if f)
    return {"by": by, "taxonomy_version": taxonomy["version"] if taxonomy else None,
            "modes": modes, "groups": groups}


def render_report(rep: dict, names: dict[str, str] | None = None) -> str:
    names = names or {}
    groups = rep["groups"]
    if not groups:
        return "corpus is empty"
    cols = list(groups)
    w = max(24, *(len(c) for c in cols))
    lines = [f"by {rep['by']}; taxonomy v{rep['taxonomy_version']}" if rep["taxonomy_version"]
             else f"by {rep['by']}; no taxonomy yet (data/taxonomy.json) — verdicts only"]
    lines.append(f"{'':<34}" + "".join(f"{c:>{w}}" for c in cols))

    def row(label: str, cells: list[str]) -> None:
        lines.append(f"{label[:33]:<34}" + "".join(f"{c:>{w}}" for c in cells))

    row("plans", [str(groups[c]["plans"]) for c in cols])
    row("reviewed (pass/fail/defer)",
        [f"{g['reviewed']} ({g['pass']}/{g['fail']}/{g['defer']})" for g in (groups[c] for c in cols)])
    for m in rep["modes"]:
        cells = []
        for c in cols:
            s = groups[c]["modes"][m]
            cells.append(f"{s['present']}/{s['labelled']}" if s["labelled"] else "-")
        row(names.get(m, m), cells)
    if rep["modes"]:
        lines.append("\nmode cells: plans with the mode / plans labelled for it ('-' = none labelled yet)")
    return "\n".join(lines)
