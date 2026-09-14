"""`evals view`: a local web page over a run directory.

`REPORT.md` is the reading aid; this is the reading *room*. It exists because
the judgement in this harness is a human comparing outputs, and the outputs
that matter most are rendered documents — an HTML epic built from
pd-components is unreadable as source and unopenable from a markdown table of
paths. The viewer puts each cell's rendered output in its own column, the two
installed skill trees under a diff, and a place to write down what was seen
that can be pasted straight back into the conversation that asked for the run.

Three rules it keeps, all inherited from `report.py`:

  * **It never judges.** No score, no verdict, no highlighting of a "winner".
    The comments are the reader's; the page only carries them.
  * **It never invents evidence.** A cell's outputs come from the same
    `report.workspace_outputs` the report used, against the same seed, so the
    page and `REPORT.md` cannot disagree about what the agent produced.
  * **It never serves outside the run directory.** The file endpoint resolves
    every path and refuses one that lands elsewhere — the run tree is the
    evidence, and a viewer bound to localhost is still a file server.

The request handling is a plain function, `handle`, that the HTTP layer wraps.
That is what keeps it testable without sockets: a test builds a real run with
the stub runner and calls `handle` on it, and the one socket test only proves
the wrapper is wired.

Dependency-free by design (stdlib `http.server` + `json`): the module's
`pyproject.toml` declares no dependencies and the viewer must not be the thing
that changes that. The page's own libraries (`marked`, `diff2html`) come from
a CDN, pinned, so an offline machine still gets the raw text and the diffs as
`<pre>`.
"""

from __future__ import annotations

import difflib
import http.server
import json
import re
import mimetypes
import socketserver
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .. import arms as arms_mod
from .. import invocation as invocation_mod
from .. import manifest as manifest_mod
from .. import paths, report

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9175

STATIC_DIR = Path(__file__).resolve().parent / "static"
COMMENTS_NAME = "comments.json"

# The fields a comment must carry. Everything a comment holds is a string —
# including `trial` — so the copy block and the sidebar never have to guess a
# type, and so "is this a valid comments file" is one rule.
COMMENT_REQUIRED = ("id", "text")

# How much of a tool call's key input the transcript tab shows. Enough to
# recognise a path or a command, not enough to become the transcript.
TOOL_SUMMARY_CHARS = 120

# Files worth reading as text for a diff. Past this the page is not something
# a human is going to read side by side; refuse rather than stall the browser.
MAX_DIFF_BYTES = 4_000_000

# Content types the guesser gets wrong or does not know. `.md` must not fall
# through to octet-stream, and `.jsonl` has no registered type at all.
_CONTENT_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".jsonl": "application/x-ndjson",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".sh": "text/x-shellscript",
    ".py": "text/x-python",
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".htm": "text/html",
}


@dataclass(frozen=True)
class Response:
    """What `handle` returns: everything the HTTP layer needs to write, and
    nothing it has to interpret."""

    status: int
    content_type: str
    body: bytes

    @staticmethod
    def json(payload, status: int = 200) -> "Response":
        return Response(
            status,
            "application/json; charset=utf-8",
            (json.dumps(payload, indent=2) + "\n").encode(),
        )

    @staticmethod
    def error(status: int, message: str) -> "Response":
        """Every failure is JSON with an `error` key, so the page can show
        the message rather than a status code."""
        return Response.json({"error": message}, status)


# --- run lookup --------------------------------------------------------------


def _runs_root(runs_dir: Path | None) -> Path:
    """`runs_dir` if given, else `paths.RUNS_DIR` read at call time so a test
    that relocates it is honoured."""
    return runs_dir if runs_dir is not None else paths.runs_root()


def _run_dir(runs_dir: Path, run_id: str) -> Path | None:
    """The run's directory, or None if there is no such run.

    A run id is a single path segment. Anything else — a slash, `..`, an
    empty string — is not a run id, and is refused before it is ever joined
    to a path.
    """
    if not run_id or "/" in run_id or run_id in (".", "..") or "\\" in run_id:
        return None
    candidate = paths.run_dir(runs_dir, run_id)
    if not candidate.is_dir():
        return None
    return candidate


def _within(root: Path, rel: str) -> Path | None:
    """`root/rel` if it resolves to a file inside `root`, else None.

    Resolved on both sides, so a symlink inside the run tree that points out
    of it is refused the same as `..` and an absolute path are. A symlink that
    points *within* the tree is fine — it resolves inside.
    """
    if not rel:
        return None
    base = root.resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(base):
        return None
    return target


# --- describing a run ---------------------------------------------------------


def _cell_dirs(run_dir: Path, arm_dir_name: str) -> list[Path]:
    arm_dir = run_dir / arm_dir_name
    if not arm_dir.is_dir():
        return []
    return sorted(
        (p for p in arm_dir.iterdir() if p.is_dir() and p.name.isdigit()),
        key=lambda p: int(p.name),
    )


def _rel(path: Path, run_dir: Path) -> str:
    return path.relative_to(run_dir).as_posix()


def _file_presence(path: Path) -> dict:
    if not path.is_file():
        return {"present": False, "size": 0}
    return {"present": True, "size": path.stat().st_size}


def _cost(envelope: dict | None) -> dict | None:
    """The three numbers a column header shows, or None when the transcript
    never reached its `result` event (a killed run; a stub has zeros)."""
    if envelope is None:
        return None
    return {
        "total_cost_usd": envelope.get("total_cost_usd"),
        "duration_ms": envelope.get("duration_ms"),
        "num_turns": envelope.get("num_turns"),
    }


def _exit_code(envelope: dict | None) -> int | None:
    """Read back the same way `report.rebuild` does: the true code is not on
    disk, so this is `is_error` from the envelope, and None when there is
    no envelope to read."""
    if envelope is None:
        return None
    return 1 if envelope.get("is_error") else 0


def _output_json(out: report.OutputFile, cell_dir: Path) -> dict:
    ws = cell_dir / "ws"
    try:
        ws_rel = out.path.relative_to(ws).as_posix()
    except ValueError:
        ws_rel = out.path.name
    return {
        "rel": out.rel,
        "ws_rel": ws_rel,
        "name": out.path.name,
        "type": out.type_name,
        "size": out.size,
        "lines": out.lines,
        "binary": out.binary,
    }


# The cell's temp dir when the transcript carries no `cwd` — the shape
# `cell.run_cell` creates (`mktemp -d` with the `evals-` prefix).
_CELL_TMP = re.compile(r"/(?:tmp|var/tmp)/evals-[A-Za-z0-9_-]+")


def _path_rewrites(stream_path: Path) -> list[tuple[str, str]]:
    """Prefixes to strip so paths read relative to the workspace.

    The workspace is `<cell>/ws` and the relocated config dir `<cell>/config`;
    both sit under a per-cell temp dir that differs in every cell and tells a
    reader nothing. Read off the init event's `cwd` when there is one, so the
    rewrite is exact; otherwise fall back to the shape the cell creates.
    Longest prefix first, so `…/ws/` is stripped before `…/` could be.
    """
    init = invocation_mod.init_event(stream_path) if stream_path.is_file() else None
    cwd = init.get("cwd") if isinstance(init, dict) else None
    if isinstance(cwd, str) and cwd.rstrip("/").endswith("/ws"):
        cell = cwd.rstrip("/")[: -len("/ws")]
    else:
        cell = None
    cells = [cell] if cell else []
    return [(c, "") for c in cells]


def _relativise(text: str, cell: str | None) -> str:
    """Strip the cell's temp-dir prefixes: `<cell>/ws/x` -> `x`,
    `<cell>/config/skills/x` -> `<skills>/x`, `<cell>/config/x` -> `<config>/x`.
    Applied everywhere in the string — a Bash command names paths mid-line."""
    def sub(base: str, s: str) -> str:
        s = s.replace(base + "/ws/", "")
        s = re.sub(re.escape(base) + r"/ws(?![\w/])", ".", s)
        s = s.replace(base + "/config/skills/", "<skills>/")
        s = s.replace(base + "/config/", "<config>/")
        return s
    if cell:
        text = sub(cell, text)
    # Anything left in the cell-tmp shape (a different cell's path quoted in
    # a command, or a transcript with no init event).
    for base in {m.group(0) for m in _CELL_TMP.finditer(text)}:
        text = sub(base, text)
    return text


def _tool_summary(block: dict, cell: str | None = None) -> dict:
    """One tool call as the transcript tab lists it: the tool's name and the
    one input a reader needs to know what it did, with paths relative to the
    workspace. `full` is the untruncated form, for a tooltip."""
    name = block.get("name") if isinstance(block.get("name"), str) else "?"
    args = block.get("input") if isinstance(block.get("input"), dict) else {}
    keys = {
        "Read": ("file_path",),
        "Write": ("file_path",),
        "Edit": ("file_path",),
        "MultiEdit": ("file_path",),
        "NotebookEdit": ("notebook_path",),
        "Bash": ("command",),
        "Skill": ("skill", "command", "name"),
        "Glob": ("pattern",),
        "Grep": ("pattern",),
        "WebFetch": ("url",),
        "WebSearch": ("query",),
        "Task": ("description", "prompt"),
        "Agent": ("description", "prompt"),
    }
    summary = ""
    for key in keys.get(name, ()):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            summary = value.strip()
            break
    if not summary:
        # An unknown tool: the first string input is the best available guess.
        for value in args.values():
            if isinstance(value, str) and value.strip():
                summary = value.strip()
                break
    summary = _relativise(summary.replace("\n", " ⏎ "), cell)
    full = summary
    if len(summary) > TOOL_SUMMARY_CHARS:
        summary = summary[:TOOL_SUMMARY_CHARS] + "…"
    return {"name": name, "summary": summary, "full": full}


def transcript(run_dir: Path, ref: str) -> Response:
    """The tool calls of one cell, compacted: name plus the one input that
    says what it did. Parsed by `invocation.tool_calls`, so the count here and
    the count in the run description come from the same reader."""
    record = manifest_mod.describe(run_dir)
    parsed = _parse_cell_ref(ref)
    if parsed is None:
        return Response.error(400, "cell must be <arm>/<trial>")
    arm, trial = parsed
    dir_by_arm = {a.name: a.dir_name for a in record.arms}
    cell_dir = run_dir / dir_by_arm.get(arm, arm) / str(trial)
    stream = cell_dir / "stream.jsonl"
    if not cell_dir.is_dir():
        return Response.error(404, f"no cell {ref} in run {record.run_id}")
    rewrites = _path_rewrites(stream)
    cell = rewrites[0][0] if rewrites else None
    calls = [_tool_summary(b, cell) for b in invocation_mod.tool_calls(stream)] if stream.is_file() else []
    counts: dict[str, int] = {}
    for c in calls:
        counts[c["name"]] = counts.get(c["name"], 0) + 1
    by_tool = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return Response.json({
        "cell": ref,
        "workspace": cell + "/ws" if cell else None,
        "calls": calls,
        "by_tool": [{"name": n, "count": k} for n, k in by_tool],
    })


def _invocation_by_trial(arm_dir: Path) -> dict[int, bool]:
    """trial -> invoked, off the arm's `invocation.json`. Read, never
    recomputed: the record written at run time is the evidence."""
    data = manifest_mod.read_json(arm_dir / invocation_mod.INVOCATION_NAME) or {}
    cells = data.get("cells") if isinstance(data.get("cells"), list) else []
    out: dict[int, bool] = {}
    for cell in cells:
        if isinstance(cell, dict) and isinstance(cell.get("trial"), int):
            out[cell["trial"]] = bool(cell.get("invoked"))
    return out


def describe_cell(run_dir: Path, arm: str, cell_dir: Path, seed: Path | None) -> dict:
    """One cell as the page sees it. Outputs come from the report's own
    seed diff, so the page never lists a file the report would not."""
    stream = cell_dir / "stream.jsonl"
    envelope = invocation_mod.result_envelope(stream) if stream.is_file() else None
    outputs = report.workspace_outputs(cell_dir, run_dir, seed)
    return {
        "arm": arm,
        "trial": int(cell_dir.name),
        "dir": _rel(cell_dir, run_dir),
        "exit_code": _exit_code(envelope),
        "cost": _cost(envelope),
        "out_md": _file_presence(cell_dir / "out.md"),
        "err_txt": _file_presence(cell_dir / "err.txt"),
        "stream": _file_presence(stream),
        "tool_calls": len(invocation_mod.tool_calls(stream)) if stream.is_file() else 0,
        "skill_installed": (cell_dir / "skill").is_dir(),
        "outputs": [_output_json(o, cell_dir) for o in outputs],
        "outputs_diffed": seed is not None and seed.is_dir(),
    }


def describe_run(run_dir: Path) -> dict:
    """The whole run: manifest, arms with provenance and verdict, every cell."""
    record = manifest_mod.describe(run_dir)
    seed = Path(record.seed) if record.seed else None

    arms_out = []
    cells_out = []
    for arm in record.arms:
        arm_dir = run_dir / arm.dir_name
        per_arm = manifest_mod.read_json(arm_dir / arms_mod.MANIFEST_NAME) or {}
        verdict = manifest_mod.read_json(arm_dir / invocation_mod.INVOCATION_NAME)
        arms_out.append(
            {
                "name": arm.name,
                "dir": arm.dir_name,
                "kind": arm.kind,
                "sha": arm.sha,
                "head": arm.head,
                "dirty": arm.dirty,
                "source": arm.source,
                "with": per_arm.get("with") if isinstance(per_arm.get("with"), list) else [],
                "invocation": (
                    {
                        "invoked": bool(verdict.get("invoked")),
                        "missed_trials": verdict.get("missed_trials") or [],
                    }
                    if verdict
                    else None
                ),
            }
        )
        invoked = _invocation_by_trial(arm_dir)
        for cell_dir in _cell_dirs(run_dir, arm.dir_name):
            cell = describe_cell(run_dir, arm.name, cell_dir, seed)
            cell["invoked"] = invoked.get(cell["trial"])
            cells_out.append(cell)

    return {
        "run": {
            "id": record.run_id,
            "skill": record.skill,
            "model": record.model,
            "runner": record.runner,
            "invoke": record.invoke,
            "trials": record.trials,
            "scenario": record.scenario,
            "with": record.with_skills,
            "seed": record.seed,
            "seed_present": bool(seed and seed.is_dir()),
            "prompt": record.prompt,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "status": record.status,
            "complete_record": record.complete_record,
            "report": (run_dir / report.REPORT_NAME).is_file(),
        },
        "arms": arms_out,
        "cells": cells_out,
    }


def list_runs(runs_dir: Path) -> list[dict]:
    """Every run, newest first — the same order and the same source of truth
    as `evals list`."""
    rows = []
    for run in paths.list_runs(runs_dir):
        record = manifest_mod.describe(run)
        rows.append(
            {
                "id": record.run_id,
                "status": record.status if record.complete_record else "no manifest",
                "skill": record.skill,
                "arms": record.arm_names,
                "trials": record.trials,
                "scenario": record.scenario,
                "started_at": record.started_at,
                "finished_at": record.finished_at,
            }
        )
    return rows


# --- diffs -------------------------------------------------------------------


def _skill_tree(run_dir: Path, arm_dir_name: str) -> dict[str, Path]:
    """`skill/**` and `with/**` of the arm's first cell, keyed by path.

    The first cell, because the snapshot is taken before the agent runs and is
    the same in every trial — it is the arm's installed tree, not the cell's.
    The `none` arm has neither directory and comes back as an empty tree,
    which is the truthful answer: nothing was installed.
    """
    cells = _cell_dirs(run_dir, arm_dir_name)
    if not cells:
        return {}
    tree: dict[str, Path] = {}
    for top in ("skill", "with"):
        root = cells[0] / top
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file():
                tree[f"{top}/{p.relative_to(root).as_posix()}"] = p
    return tree


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def _unified(a_text: str, b_text: str, a_label: str, b_label: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            a_text.splitlines(),
            b_text.splitlines(),
            fromfile=a_label,
            tofile=b_label,
            lineterm="",
        )
    )


def skill_diff(run_dir: Path, arm_a: str, arm_b: str) -> list[dict]:
    """Per file: added / removed / changed / same between two arms' installed
    trees, with a unified diff for anything that differs."""
    tree_a = _skill_tree(run_dir, arm_a)
    tree_b = _skill_tree(run_dir, arm_b)
    rows = []
    for path in sorted(set(tree_a) | set(tree_b)):
        in_a, in_b = path in tree_a, path in tree_b
        raw_a = tree_a[path].read_bytes() if in_a else b""
        raw_b = tree_b[path].read_bytes() if in_b else b""
        if not in_a:
            status = "added"
        elif not in_b:
            status = "removed"
        elif raw_a == raw_b:
            status = "same"
        else:
            status = "changed"
        binary = _is_binary(raw_a) or _is_binary(raw_b)
        diff = ""
        if status != "same" and not binary:
            diff = _unified(
                raw_a.decode("utf-8", errors="replace"),
                raw_b.decode("utf-8", errors="replace"),
                f"a/{arm_a}/{path}",
                f"b/{arm_b}/{path}",
            )
        rows.append({"path": path, "status": status, "binary": binary, "diff": diff})
    return rows


def _parse_cell_ref(ref: str) -> tuple[str, int] | None:
    """`WORKTREE/2` -> ("WORKTREE", 2)."""
    arm, sep, trial = ref.rpartition("/")
    if not sep or not arm or not trial.isdigit():
        return None
    return arm, int(trial)


def _primary_output(run_dir: Path, cell_dir: Path, seed: Path | None) -> str | None:
    outputs = report.workspace_outputs(cell_dir, run_dir, seed)
    if not outputs:
        return None
    return _output_json(outputs[0], cell_dir)["ws_rel"]


def output_diff(
    run_dir: Path, ref_a: str, ref_b: str, file: str | None
) -> Response:
    """A unified diff of one workspace file between two cells.

    With no `file`, each side's primary output is used — and when the two
    primaries have different names (two trials that named the epic
    differently) they are diffed anyway, with `same_name: false` and a note,
    because "the same deliverable under a different name" is exactly what a
    reader wants to compare. A file missing on one side diffs against empty.
    """
    record = manifest_mod.describe(run_dir)
    seed = Path(record.seed) if record.seed else None
    parsed = [_parse_cell_ref(ref_a), _parse_cell_ref(ref_b)]
    if None in parsed:
        return Response.error(400, "a and b must be <arm>/<trial>")
    dir_by_arm = {a.name: a.dir_name for a in record.arms}
    sides = []
    for (arm, trial), ref in zip(parsed, (ref_a, ref_b)):
        cell_dir = run_dir / dir_by_arm.get(arm, arm) / str(trial)
        if not cell_dir.is_dir():
            return Response.error(404, f"no cell {ref} in run {record.run_id}")
        rel = file or _primary_output(run_dir, cell_dir, seed)
        sides.append({"cell": ref, "cell_dir": cell_dir, "file": rel})

    if any(s["file"] is None for s in sides):
        return Response.error(
            400,
            "no primary output to diff on one side; pass file=<path within ws/>",
        )

    texts = []
    for side in sides:
        target = _within(side["cell_dir"] / "ws", side["file"])
        if target is None or not target.is_file():
            side["present"] = False
            texts.append("")
            continue
        if target.stat().st_size > MAX_DIFF_BYTES:
            return Response.error(400, f"{side['file']} is too large to diff")
        raw = target.read_bytes()
        if _is_binary(raw):
            return Response.error(
                400, f"{side['cell']}/ws/{side['file']} is binary; nothing to diff"
            )
        side["present"] = True
        texts.append(raw.decode("utf-8", errors="replace"))

    a, b = sides
    same_name = a["file"] == b["file"]
    note = None
    if not same_name:
        note = (
            f"the two primaries have different names — diffing "
            f"{a['file']} against {b['file']}"
        )
    if not a["present"] or not b["present"]:
        missing = [s["cell"] for s in sides if not s["present"]]
        note = f"missing in {', '.join(missing)}; diffed against an empty file"
    diff = _unified(
        texts[0], texts[1], f"a/{a['cell']}/{a['file']}", f"b/{b['cell']}/{b['file']}"
    )
    return Response.json(
        {
            "a": {"cell": a["cell"], "file": a["file"], "present": a["present"]},
            "b": {"cell": b["cell"], "file": b["file"], "present": b["present"]},
            "same_name": same_name,
            "identical": texts[0] == texts[1],
            "note": note,
            "diff": diff,
        }
    )


# --- comments -----------------------------------------------------------------


def read_comments(run_dir: Path) -> list[dict]:
    """The run's comments, or an empty list when none have been written.
    A damaged file reads as empty rather than as a failure to load the run."""
    try:
        data = json.loads((run_dir / COMMENTS_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def validate_comments(body: bytes) -> list[dict] | str:
    """The list, or the reason it was refused.

    A comments file is a JSON array of flat string-valued objects, every one
    carrying an `id` and a `text`. Strict on purpose: the file is also what
    the copy block is built from, and a comment with a nested value or a
    numeric trial would render differently in the two places.
    """
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"body is not JSON: {exc}"
    if not isinstance(data, list):
        return "body must be a JSON array"
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return f"comment {i} is not an object"
        for key, value in item.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return f"comment {i}: field {key!r} must be a string"
        for key in COMMENT_REQUIRED:
            if key not in item:
                return f"comment {i} has no {key!r}"
    return data


def write_comments(run_dir: Path, comments: list[dict]) -> None:
    (run_dir / COMMENTS_NAME).write_text(json.dumps(comments, indent=2) + "\n")


# --- the file endpoint ----------------------------------------------------------


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    ctype = _CONTENT_TYPES.get(suffix) or mimetypes.guess_type(path.name)[0]
    if ctype is None:
        ctype = "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/json", "application/x-ndjson"):
        ctype += "; charset=utf-8"
    return ctype


def serve_file(run_dir: Path, rel: str) -> Response:
    """Any file inside the run directory, with its real content type.

    HTML goes out as `text/html` on purpose: the page renders it in a
    sandboxed iframe, and the whole point of the viewer is seeing the
    document rather than its source. Outside the run directory is 403 even
    when the file exists — the answer to "can I read /etc/passwd through
    this" must not depend on whether it is there.
    """
    if not rel:
        return Response.error(400, "path is required")
    target = _within(run_dir, rel)
    if target is None:
        return Response.error(403, "path resolves outside the run directory")
    if not target.is_file():
        return Response.error(404, f"no file {rel} in run {run_dir.name}")
    return Response(200, content_type_for(target), target.read_bytes())


def _static(name: str) -> Response:
    target = _within(STATIC_DIR, name)
    if target is None or not target.is_file() or target.parent != STATIC_DIR.resolve():
        return Response.error(404, f"no static file {name}")
    return Response(200, content_type_for(target), target.read_bytes())


# --- routing ---------------------------------------------------------------------


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or [""]
    return values[0]


def handle(
    method: str,
    path: str,
    query: dict[str, list[str]] | None = None,
    body: bytes = b"",
    runs_dir: Path | None = None,
) -> Response:
    """Route one request. Pure in the sense that matters: no socket, no
    global state beyond the run directory it reads (and, for a comments
    PUT, writes)."""
    query = query or {}
    runs_dir = _runs_root(runs_dir)
    parts = [p for p in path.split("/") if p]

    # The page. `/` and `/run/<id>` are the same document; the app reads the
    # id off the URL, so a run link is bookmarkable.
    if method == "GET" and (not parts or (parts[0] == "run" and len(parts) == 2)):
        return _static("index.html")
    if method == "GET" and len(parts) == 2 and parts[0] == "static":
        return _static(parts[1])

    if not parts or parts[0] != "api":
        return Response.error(404, f"no route {path}")
    if len(parts) < 2 or parts[1] != "runs":
        return Response.error(404, f"no route {path}")

    if len(parts) == 2:
        if method != "GET":
            return Response.error(405, "GET only")
        return Response.json(list_runs(runs_dir))

    run_dir = _run_dir(runs_dir, parts[2])
    if run_dir is None:
        return Response.error(404, f"no run {parts[2]!r} under {runs_dir}")
    rest = parts[3:]

    if not rest:
        if method != "GET":
            return Response.error(405, "GET only")
        return Response.json(describe_run(run_dir))

    if rest == ["file"] and method == "GET":
        return serve_file(run_dir, _first(query, "path"))

    if rest == ["skill-diff"] and method == "GET":
        record = manifest_mod.describe(run_dir)
        dir_by_arm = {a.name: a.dir_name for a in record.arms}
        a, b = _first(query, "a"), _first(query, "b")
        if not a or not b:
            return Response.error(400, "a and b (arm names) are required")
        for name in (a, b):
            if name not in dir_by_arm:
                return Response.error(404, f"no arm {name!r} in run {record.run_id}")
        return Response.json(
            {"a": a, "b": b, "files": skill_diff(run_dir, dir_by_arm[a], dir_by_arm[b])}
        )

    if rest == ["output-diff"] and method == "GET":
        a, b = _first(query, "a"), _first(query, "b")
        if not a or not b:
            return Response.error(400, "a and b (<arm>/<trial>) are required")
        return output_diff(run_dir, a, b, _first(query, "file") or None)

    if rest == ["transcript"] and method == "GET":
        ref = _first(query, "cell")
        if not ref:
            return Response.error(400, "cell (<arm>/<trial>) is required")
        return transcript(run_dir, ref)

    if rest == ["comments"]:
        if method == "GET":
            return Response.json(read_comments(run_dir))
        if method == "PUT":
            checked = validate_comments(body)
            if isinstance(checked, str):
                return Response.error(400, checked)
            write_comments(run_dir, checked)
            return Response.json(checked)
        return Response.error(405, "GET or PUT")

    return Response.error(404, f"no route {path}")


# --- the HTTP layer -----------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    """The thinnest wrapper over `handle`: parse the URL, read the body,
    write the response. Nothing here decides anything."""

    server: "ViewerServer"

    def _dispatch(self, method: str) -> None:
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            resp = handle(
                method, url.path, parse_qs(url.query, keep_blank_values=True),
                body, self.server.runs_dir,
            )
        except Exception as exc:  # a bug must not take the server down
            resp = Response.error(500, f"{type(exc).__name__}: {exc}")
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(resp.body)

    def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
        self._dispatch("GET")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if self.server.quiet:
            return
        sys.stderr.write("evals view: %s\n" % (format % args))


class ViewerServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """An HTTP server that knows which runs directory it is serving."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], runs_dir: Path, quiet: bool = False):
        super().__init__(address, _Handler)
        self.runs_dir = runs_dir
        self.quiet = quiet

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"


def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    runs_dir: Path | None = None,
    quiet: bool = False,
) -> ViewerServer:
    """Bind, and return without serving. Port 0 picks a free one, which is
    what a test wants; the CLI uses the fixed default so the URL is stable."""
    return ViewerServer((host, port), _runs_root(runs_dir), quiet=quiet)


def serve_in_thread(server: ViewerServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
