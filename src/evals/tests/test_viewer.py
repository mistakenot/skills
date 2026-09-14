"""`evals view`: the JSON API over a run directory, tested without sockets.

Every test here runs the real CLI in stub mode into a relocated `runs/`, then
calls `viewer.handle` on what it left — the routing is a plain function, and
the HTTP layer is a wrapper thin enough that one socket test proves it is
wired. Arm resolution is the one part stood in for, as everywhere else in
this suite: `arms.resolve` shells out to the compiler and rewrites the repo's
`skills/` tree, which a test must not do.

The file endpoint is a file server bound to localhost, and a file server is
where "it's only local" goes wrong. So the traversal tests are the ones that
try hardest: `..`, an absolute path, and a symlink planted *inside* the run
tree that points out of it.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest

from evals import __main__ as cli
from evals import arms, manifest, paths, runners, viewer
from evals.viewer import server as viewer_server

HEAD_SHA = "b" * 40


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    """A relocated `runs/`, and two compiled skill trees that differ so that
    two installed arms have something to diff."""
    base = tmp_path / "compiled" / "base"
    (base / "references").mkdir(parents=True)
    (base / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (base / "references" / "extra.md").write_text("detail\n")
    (base / "references" / "gone.md").write_text("only in base\n")

    edited = tmp_path / "compiled" / "edited"
    (edited / "references").mkdir(parents=True)
    (edited / "SKILL.md").write_text("---\nname: demo\n---\nbody, edited\n")
    (edited / "references" / "extra.md").write_text("detail\n")
    (edited / "references" / "new.md").write_text("only in edited\n")

    def fake_resolve(arm, skill):
        if arm == arms.NONE:
            return arms.Arm(name=arm, kind=arms.KIND_NONE, skill_src=None)
        if arm == arms.WORKTREE:
            return arms.Arm(
                name=arm, kind=arms.KIND_WORKTREE, skill_src=edited,
                sha=arms.WORKTREE, head=HEAD_SHA, dirty=True,
            )
        return arms.Arm(name=arm, kind=arms.KIND_REF, skill_src=base, sha="a" * 40)

    monkeypatch.setattr(arms, "resolve", fake_resolve)
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return tmp_path / "runs"


def _run(capsys, *extra, arm_names=(arms.NONE, "HEAD", arms.WORKTREE)):
    argv = ["run", "--skill", "demo"]
    for name in arm_names:
        argv += ["--arm", name]
    argv += ["--prompt", "write me an answer", "--runner", runners.STUB, *extra]
    assert cli.main(argv) == 0
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("evals: run "):
            return line.split()[2]
    raise AssertionError("the run never announced its id")


def _get(path, query=None, runs_dir=None):
    return viewer.handle("GET", path, query or {}, b"", runs_dir)


def _json(resp):
    assert resp.content_type.startswith("application/json"), resp.content_type
    return json.loads(resp.body)


# --- run list and description ---------------------------------------------------


def test_run_list_is_newest_first_with_the_fields_the_page_needs(runs_dir, capsys):
    first = _run(capsys, arm_names=(arms.WORKTREE,))
    second = _run(capsys, "--n", "2", arm_names=(arms.NONE, arms.WORKTREE))
    resp = _get("/api/runs")
    assert resp.status == 200
    rows = _json(resp)
    assert [r["id"] for r in rows] == [second, first]
    assert rows[0]["arms"] == [arms.NONE, arms.WORKTREE]
    assert rows[0]["trials"] == 2
    assert rows[0]["skill"] == "demo"
    assert rows[0]["status"] == "ok"
    assert rows[0]["started_at"] and rows[0]["finished_at"]


def test_run_list_honours_a_runs_dir_argument(runs_dir, capsys, tmp_path):
    _run(capsys, arm_names=(arms.WORKTREE,))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert _json(_get("/api/runs", runs_dir=elsewhere)) == []
    assert len(_json(_get("/api/runs", runs_dir=runs_dir))) == 1


def test_unknown_run_is_404_everywhere(runs_dir, capsys):
    _run(capsys, arm_names=(arms.WORKTREE,))
    for path in (
        "/api/runs/nope",
        "/api/runs/nope/file",
        "/api/runs/nope/skill-diff",
        "/api/runs/nope/output-diff",
        "/api/runs/nope/comments",
        "/api/runs/nope/transcript",
    ):
        resp = _get(path, {"path": ["x"], "a": ["x"], "b": ["y"], "cell": ["x/1"]})
        assert resp.status == 404, path
        assert "error" in _json(resp)
    assert viewer.handle("PUT", "/api/runs/nope/comments", {}, b"[]").status == 404
    assert _get("/api/runs/../etc").status == 404


def test_run_description_carries_arms_cells_and_verdicts(runs_dir, capsys):
    run_id = _run(capsys, "--n", "2")
    data = _json(_get(f"/api/runs/{run_id}"))

    assert data["run"]["id"] == run_id
    assert data["run"]["skill"] == "demo"
    assert data["run"]["trials"] == 2
    assert data["run"]["report"] is True
    assert data["run"]["seed"] is None

    by_name = {a["name"]: a for a in data["arms"]}
    assert by_name[arms.NONE]["kind"] == arms.KIND_NONE
    assert by_name[arms.WORKTREE]["kind"] == arms.KIND_WORKTREE
    assert by_name[arms.WORKTREE]["head"] == HEAD_SHA
    assert by_name[arms.WORKTREE]["dirty"] is True
    assert by_name["HEAD"]["sha"] == "a" * 40
    assert by_name[arms.WORKTREE]["invocation"]["invoked"] is True
    assert by_name[arms.NONE]["invocation"]["invoked"] is False

    assert [(c["arm"], c["trial"]) for c in data["cells"]] == [
        (arms.NONE, 1), (arms.NONE, 2), ("HEAD", 1), ("HEAD", 2),
        (arms.WORKTREE, 1), (arms.WORKTREE, 2),
    ]
    cell = next(c for c in data["cells"] if c["arm"] == arms.WORKTREE and c["trial"] == 2)
    assert cell["dir"] == f"{arms.WORKTREE}/2"
    assert cell["exit_code"] == 0
    assert cell["invoked"] is True
    assert cell["skill_installed"] is True
    assert cell["out_md"]["present"] and cell["out_md"]["size"] > 0
    assert cell["err_txt"]["present"] is True
    assert cell["cost"] == {"total_cost_usd": 0.0, "duration_ms": 0, "num_turns": cell["cost"]["num_turns"]}
    # The stub makes Skill, Read, Bash and Write calls on an installed arm.
    assert cell["tool_calls"] == 4
    # No seed: the root heuristic, and the stub writes answer.md at the root.
    assert cell["outputs_diffed"] is False
    assert [o["ws_rel"] for o in cell["outputs"]] == ["answer.md"]
    assert cell["outputs"][0]["rel"] == f"{arms.WORKTREE}/2/ws/answer.md"
    assert cell["outputs"][0]["type"] == "Markdown"

    none_cell = next(c for c in data["cells"] if c["arm"] == arms.NONE)
    assert none_cell["skill_installed"] is False
    assert none_cell["invoked"] is False


def test_outputs_come_from_the_seed_diff_when_the_run_has_a_seed(runs_dir, capsys, tmp_path):
    """The page must list what the report lists: with a seed, every file new
    or changed anywhere in the tree — not just the `ws/` root."""
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    run_dir = runs_dir / run_id
    cell_dir = run_dir / arms.WORKTREE / "1"

    seed = tmp_path / "seed"
    (seed / "repo" / "docs").mkdir(parents=True)
    (seed / "repo" / "README.md").write_text("fixture\n")
    (seed / "repo" / "docs" / "old.md").write_text("old\n")
    ws = cell_dir / "ws"
    (ws / "repo" / "docs").mkdir(parents=True)
    (ws / "repo" / "README.md").write_text("fixture\n")            # untouched
    (ws / "repo" / "docs" / "old.md").write_text("old, edited\n")   # changed
    (ws / "repo" / "docs" / "epic-001.html").write_text("<pd-doc></pd-doc>\n")  # added

    # Stamp the seed into the manifest the way a scenario run would have.
    data = json.loads((run_dir / manifest.RUN_MANIFEST_NAME).read_text())
    data["seed"] = str(seed)
    (run_dir / manifest.RUN_MANIFEST_NAME).write_text(json.dumps(data))

    cell = _json(_get(f"/api/runs/{run_id}"))["cells"][0]
    assert cell["outputs_diffed"] is True
    names = {o["ws_rel"] for o in cell["outputs"]}
    # answer.md is the stub's own root file, which is also new against the seed.
    assert names == {"answer.md", "repo/docs/old.md", "repo/docs/epic-001.html"}
    html = next(o for o in cell["outputs"] if o["name"] == "epic-001.html")
    assert html["type"] == "HTML"
    assert html["rel"] == f"{arms.WORKTREE}/1/ws/repo/docs/epic-001.html"


def test_a_run_without_a_manifest_still_describes(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    (runs_dir / run_id / manifest.RUN_MANIFEST_NAME).unlink()
    data = _json(_get(f"/api/runs/{run_id}"))
    assert data["run"]["complete_record"] is False
    assert [a["name"] for a in data["arms"]] == [arms.WORKTREE]
    assert len(data["cells"]) == 1


# --- the file endpoint -------------------------------------------------------------


def test_file_endpoint_serves_html_as_text_html(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    ws = runs_dir / run_id / arms.WORKTREE / "1" / "ws"
    (ws / "doc.html").write_text("<pd-doc>hi</pd-doc>")
    resp = _get(f"/api/runs/{run_id}/file", {"path": [f"{arms.WORKTREE}/1/ws/doc.html"]})
    assert resp.status == 200
    assert resp.content_type == "text/html; charset=utf-8"
    assert resp.body == b"<pd-doc>hi</pd-doc>"


def test_file_endpoint_types_markdown_and_transcripts(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    md = _get(f"/api/runs/{run_id}/file", {"path": ["REPORT.md"]})
    assert md.status == 200 and md.content_type == "text/markdown; charset=utf-8"
    jsonl = _get(f"/api/runs/{run_id}/file", {"path": [f"{arms.WORKTREE}/1/stream.jsonl"]})
    assert jsonl.status == 200 and jsonl.content_type == "application/x-ndjson; charset=utf-8"


def test_file_endpoint_refuses_paths_outside_the_run(runs_dir, capsys, tmp_path):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    run_dir = runs_dir / run_id
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours\n")
    # A symlink planted inside the run tree that points out of it.
    (run_dir / "escape").symlink_to(secret)
    (run_dir / "escape-dir").symlink_to(tmp_path)

    for rel in (
        "../secret.txt",
        "../../secret.txt",
        f"{arms.WORKTREE}/../../secret.txt",
        str(secret),                         # absolute
        "/etc/passwd",
        "escape",                            # symlink to a file outside
        "escape-dir/secret.txt",             # through a symlinked directory
    ):
        resp = _get(f"/api/runs/{run_id}/file", {"path": [rel]})
        assert resp.status == 403, rel
        assert b"not yours" not in resp.body
        assert "error" in _json(resp)

    # And the same rule for a run id that is not a plain segment.
    assert _get("/api/runs/../secret.txt/file", {"path": ["x"]}).status == 404

    # A file that is simply not there is 404, and an empty path is 400.
    assert _get(f"/api/runs/{run_id}/file", {"path": ["nope.md"]}).status == 404
    assert _get(f"/api/runs/{run_id}/file", {}).status == 400
    # A directory is not a file.
    assert _get(f"/api/runs/{run_id}/file", {"path": [arms.WORKTREE]}).status == 404


def test_file_endpoint_follows_symlinks_that_stay_inside(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    run_dir = runs_dir / run_id
    (run_dir / "alias.md").symlink_to(run_dir / "REPORT.md")
    resp = _get(f"/api/runs/{run_id}/file", {"path": ["alias.md"]})
    assert resp.status == 200
    assert resp.body == (run_dir / "REPORT.md").read_bytes()


# --- skill diff ---------------------------------------------------------------------


def test_skill_diff_reports_added_removed_changed_and_same(runs_dir, capsys):
    run_id = _run(capsys)
    resp = _get(f"/api/runs/{run_id}/skill-diff", {"a": ["HEAD"], "b": [arms.WORKTREE]})
    assert resp.status == 200
    data = _json(resp)
    assert data["a"] == "HEAD" and data["b"] == arms.WORKTREE
    by_path = {f["path"]: f for f in data["files"]}
    assert {p: f["status"] for p, f in by_path.items()} == {
        "skill/SKILL.md": "changed",
        "skill/references/extra.md": "same",
        "skill/references/gone.md": "removed",
        "skill/references/new.md": "added",
    }
    changed = by_path["skill/SKILL.md"]["diff"]
    assert changed.startswith("--- a/HEAD/skill/SKILL.md\n+++ b/WORKTREE/skill/SKILL.md\n")
    assert "-body\n+body, edited" in changed
    assert by_path["skill/references/extra.md"]["diff"] == ""
    assert "+only in edited" in by_path["skill/references/new.md"]["diff"]
    assert "-only in base" in by_path["skill/references/gone.md"]["diff"]


def test_skill_diff_of_an_arm_against_itself_is_all_same(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    data = _json(_get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.WORKTREE], "b": [arms.WORKTREE]}))
    assert data["files"]
    assert {f["status"] for f in data["files"]} == {"same"}


def test_skill_diff_treats_the_none_arm_as_an_empty_tree(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.NONE, arms.WORKTREE))
    data = _json(_get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.NONE], "b": [arms.WORKTREE]}))
    assert data["files"]
    assert {f["status"] for f in data["files"]} == {"added"}
    both_none = _json(_get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.NONE], "b": [arms.NONE]}))
    assert both_none["files"] == []


def test_skill_diff_includes_companions(runs_dir, capsys, tmp_path):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    with_dir = runs_dir / run_id / arms.WORKTREE / "1" / "with" / "helper"
    with_dir.mkdir(parents=True)
    (with_dir / "SKILL.md").write_text("helper\n")
    data = _json(_get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.WORKTREE], "b": [arms.WORKTREE]}))
    assert "with/helper/SKILL.md" in {f["path"] for f in data["files"]}


def test_skill_diff_rejects_unknown_arms_and_missing_params(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    assert _get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.WORKTREE]}).status == 400
    assert _get(f"/api/runs/{run_id}/skill-diff", {"a": [arms.WORKTREE], "b": ["ghost"]}).status == 404


# --- output diff ---------------------------------------------------------------------


def test_output_diff_defaults_to_each_cells_primary_output(runs_dir, capsys):
    run_id = _run(capsys, "--n", "2", arm_names=(arms.WORKTREE,))
    ws2 = runs_dir / run_id / arms.WORKTREE / "2" / "ws"
    (ws2 / "answer.md").write_text("2+2=5\n")
    resp = _get(
        f"/api/runs/{run_id}/output-diff",
        {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/2"]},
    )
    assert resp.status == 200
    data = _json(resp)
    assert data["a"] == {"cell": f"{arms.WORKTREE}/1", "file": "answer.md", "present": True}
    assert data["b"]["file"] == "answer.md"
    assert data["same_name"] is True
    assert data["identical"] is False
    assert data["note"] is None
    assert "-2+2=4\n+2+2=5" in data["diff"]


def test_output_diff_diffs_primaries_with_different_names_and_says_so(runs_dir, capsys):
    """Two trials that named the epic differently are still the same
    deliverable; the diff goes ahead and the response says the names differ."""
    run_id = _run(capsys, "--n", "2", arm_names=(arms.WORKTREE,))
    ws2 = runs_dir / run_id / arms.WORKTREE / "2" / "ws"
    (ws2 / "answer.md").unlink()
    (ws2 / "reply.md").write_text("2+2=4\nand a bit more\n")
    data = _json(_get(
        f"/api/runs/{run_id}/output-diff",
        {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/2"]},
    ))
    assert data["a"]["file"] == "answer.md"
    assert data["b"]["file"] == "reply.md"
    assert data["same_name"] is False
    assert "different names" in data["note"]
    assert "+and a bit more" in data["diff"]


def test_output_diff_of_a_named_file_and_of_a_missing_one(runs_dir, capsys):
    run_id = _run(capsys, "--n", "2", arm_names=(arms.WORKTREE,))
    ws1 = runs_dir / run_id / arms.WORKTREE / "1" / "ws"
    (ws1 / "notes.txt").write_text("only in trial 1\n")
    data = _json(_get(
        f"/api/runs/{run_id}/output-diff",
        {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/2"], "file": ["notes.txt"]},
    ))
    assert data["a"]["present"] is True and data["b"]["present"] is False
    assert "missing in WORKTREE/2" in data["note"]
    assert "-only in trial 1" in data["diff"]


def test_output_diff_of_a_binary_file_is_a_json_error(runs_dir, capsys):
    run_id = _run(capsys, "--n", "2", arm_names=(arms.WORKTREE,))
    for trial in ("1", "2"):
        (runs_dir / run_id / arms.WORKTREE / trial / "ws" / "blob.bin").write_bytes(b"\x00\x01\x02")
    resp = _get(
        f"/api/runs/{run_id}/output-diff",
        {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/2"], "file": ["blob.bin"]},
    )
    assert resp.status == 400
    assert "binary" in _json(resp)["error"]


def test_output_diff_rejects_bad_cell_refs_and_escapes(runs_dir, capsys, tmp_path):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    base = {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/1"]}
    assert _get(f"/api/runs/{run_id}/output-diff", {"a": ["x"], "b": ["y"]}).status == 400
    assert _get(f"/api/runs/{run_id}/output-diff", {"a": [f"{arms.WORKTREE}/1"], "b": [f"{arms.WORKTREE}/9"]}).status == 404
    # A `file` that escapes `ws/` is treated as absent, never read.
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours\n")
    data = _json(_get(f"/api/runs/{run_id}/output-diff", {**base, "file": [str(secret)]}))
    assert data["a"]["present"] is False and "not yours" not in data["diff"]
    data = _json(_get(f"/api/runs/{run_id}/output-diff", {**base, "file": ["../../out.md"]}))
    assert data["a"]["present"] is False


# --- transcript ---------------------------------------------------------------------------


def test_transcript_lists_tool_calls_with_their_key_input(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    data = _json(_get(f"/api/runs/{run_id}/transcript", {"cell": [f"{arms.WORKTREE}/1"]}))
    names = [c["name"] for c in data["calls"]]
    assert names == ["Skill", "Read", "Bash", "Write"]
    by_name = {c["name"]: c["summary"] for c in data["calls"]}
    assert by_name["Skill"] == "demo"
    assert by_name["Read"].endswith("/skills/demo/SKILL.md")
    assert by_name["Bash"] == "ls -la"
    assert by_name["Write"].endswith("/answer.md")
    assert all(len(c["summary"]) <= viewer_server.TOOL_SUMMARY_CHARS + 1 for c in data["calls"])
    assert _get(f"/api/runs/{run_id}/transcript", {"cell": ["nope/1"]}).status == 404
    assert _get(f"/api/runs/{run_id}/transcript", {}).status == 400


# --- comments ---------------------------------------------------------------------------------


def test_comments_round_trip_and_live_in_the_run_directory(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    assert _json(_get(f"/api/runs/{run_id}/comments")) == []

    comments = [
        {
            "id": "c1", "created_at": "2026-09-14T10:00:00Z", "tab": "outputs",
            "arm": arms.WORKTREE, "trial": "1", "file": "WORKTREE/1/ws/answer.md",
            "quote": "2+2=4", "text": "correct, but terse",
        }
    ]
    body = json.dumps(comments).encode()
    put = viewer.handle("PUT", f"/api/runs/{run_id}/comments", {}, body)
    assert put.status == 200
    assert _json(put) == comments
    assert json.loads((runs_dir / run_id / viewer_server.COMMENTS_NAME).read_text()) == comments
    assert _json(_get(f"/api/runs/{run_id}/comments")) == comments

    # PUT replaces the whole array: an empty list clears.
    assert viewer.handle("PUT", f"/api/runs/{run_id}/comments", {}, b"[]").status == 200
    assert _json(_get(f"/api/runs/{run_id}/comments")) == []


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        b'[1]',
        b'[{"id": "c1"}]',                       # no text
        b'[{"text": "t"}]',                      # no id
        b'[{"id": "c1", "text": "t", "trial": 1}]',   # a non-string field
        b'[{"id": "c1", "text": ["t"]}]',
    ],
)
def test_malformed_comments_are_refused_and_nothing_is_written(runs_dir, capsys, body):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    resp = viewer.handle("PUT", f"/api/runs/{run_id}/comments", {}, body)
    assert resp.status == 400
    assert "error" in _json(resp)
    assert not (runs_dir / run_id / viewer_server.COMMENTS_NAME).exists()


def test_a_damaged_comments_file_reads_as_empty(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    (runs_dir / run_id / viewer_server.COMMENTS_NAME).write_text("{oops")
    assert _json(_get(f"/api/runs/{run_id}/comments")) == []


# --- the page and its static files -------------------------------------------------------------


def test_index_is_served_at_root_and_at_run_urls(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    for path in ("/", f"/run/{run_id}", "/run/anything"):
        resp = _get(path)
        assert resp.status == 200, path
        assert resp.content_type.startswith("text/html")
        assert b"<title>evals</title>" in resp.body
    assert _get("/static/app.js").status == 200
    assert _get("/static/style.css").content_type.startswith("text/css")
    assert _get("/static/../server.py").status == 404
    assert _get("/nope").status == 404


def test_the_page_pins_its_cdn_libraries(runs_dir):
    """Only cdnjs, and only exact versions: an unpinned library is a page
    that renders differently next month."""
    html = (viewer_server.STATIC_DIR / "index.html").read_text()
    import re
    urls = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert urls
    for url in urls:
        assert url.startswith("https://cdnjs.cloudflare.com/ajax/libs/"), url
        assert re.search(r"/\d+\.\d+\.\d+/", url), url


# --- the HTTP layer -------------------------------------------------------------------------------


def test_the_server_answers_over_a_real_socket(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.WORKTREE,))
    server = viewer.make_server("127.0.0.1", 0, runs_dir, quiet=True)
    viewer.serve_in_thread(server)
    try:
        with urllib.request.urlopen(f"{server.url}/api/runs", timeout=5) as r:
            assert r.status == 200
            assert r.headers["Content-Type"].startswith("application/json")
            rows = json.loads(r.read())
        assert [row["id"] for row in rows] == [run_id]

        with urllib.request.urlopen(
            f"{server.url}/api/runs/{run_id}/file?path=REPORT.md", timeout=5
        ) as r:
            assert r.headers["Content-Type"] == "text/markdown; charset=utf-8"
            assert b"eval run" in r.read()

        req = urllib.request.Request(
            f"{server.url}/api/runs/{run_id}/comments",
            data=b'[{"id": "c1", "text": "over the wire"}]',
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 200
        assert json.loads((runs_dir / run_id / viewer_server.COMMENTS_NAME).read_text())[0]["text"] == "over the wire"

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{server.url}/api/runs/nope", timeout=5)
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


# --- the CLI ---------------------------------------------------------------------------------------


def test_view_refuses_an_unknown_run_before_binding(runs_dir, capsys):
    assert cli.main(["view", "nope"]) == 2
    assert "no run 'nope'" in capsys.readouterr().err


def test_view_parser_defaults(runs_dir):
    args = cli.build_parser().parse_args(["view"])
    assert args.run_id is None
    assert args.port == viewer.DEFAULT_PORT
    assert args.host == viewer.DEFAULT_HOST
    assert args.runs_dir is None
    args = cli.build_parser().parse_args(["view", "abc", "--port", "9176", "--runs-dir", "/x"])
    assert (args.run_id, args.port, args.runs_dir) == ("abc", 9176, "/x")
