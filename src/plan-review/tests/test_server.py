"""The review server end to end over real HTTP (stdlib client, ephemeral port)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import corpus
import server


@pytest.fixture
def base(harbor_run: Path, tmp_path: Path):
    runs, data = tmp_path / "runs", tmp_path / "data"
    corpus.add(corpus.ingest_run(harbor_run), runs, data)
    review = server.Review(runs, data, "charlie")
    httpd = server.serve(review, "127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    host, port = httpd.server_address[:2]
    yield f"http://{host}:{port}", data
    httpd.shutdown()
    httpd.server_close()


def _get(url: str):
    with urllib.request.urlopen(url) as r:
        body = r.read()
        return r.headers.get_content_type(), body


def _post(url: str, obj) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_plan_list_is_blind(base) -> None:
    url, _ = base
    _, body = _get(f"{url}/api/plans")
    [p] = json.loads(body)
    assert p["fixture_id"] == "fx-1" and p["n"] == 1
    # No arm, skills version, trial, model or cost reaches the review screen.
    for leaked in ("arm_id", "skills_sha", "trial", "model", "cost_usd", "run"):
        assert leaked not in p
    _, body = _get(f"{url}/api/plans/{p['plan_id']}")
    detail = json.loads(body)
    assert detail["prompt"] == "/new-task-quick do it"
    assert detail["has_context"] and detail["has_transcript"]
    assert not {"arm_id", "skills_sha", "model"} & set(detail)


def test_opening_a_plan_snapshots_it(base) -> None:
    url, data = base
    [p] = json.loads(_get(f"{url}/api/plans")[1])
    assert not p["snapshotted"]
    ctype, body = _get(f"{url}/plan/{p['plan_id']}/plan.html")
    assert ctype == "text/html" and b"<pd-doc" in body
    assert (data / "plans" / p["plan_id"] / "plan.html").is_file()
    assert json.loads(_get(f"{url}/api/plans")[1])[0]["snapshotted"]
    ctype, body = _get(f"{url}/plan/{p['plan_id']}/context.md")
    assert ctype == "text/plain" and body.startswith(b"# context")


def test_events_round_trip(base) -> None:
    url, data = base
    [p] = json.loads(_get(f"{url}/api/plans")[1])
    code, res = _post(f"{url}/api/events", {
        "event": "note.create", "plan_id": p["plan_id"], "tab": "Plan",
        "quote": "retry webhooks", "prefix": "Phase 1: ", "suffix": " with backoff", "text": "no retry cap stated",
    })
    assert code == 200 and res["event"]["reviewer"] == "charlie"
    code, _ = _post(f"{url}/api/events", {"event": "verdict", "plan_id": p["plan_id"], "verdict": "fail", "text": "thin"})
    assert code == 200
    state = json.loads(_get(f"{url}/api/state")[1])
    assert state["notes"][0]["text"] == "no retry cap stated"
    assert state["verdicts"][p["plan_id"]]["verdict"] == "fail"
    assert len((data / "notes.jsonl").read_text().splitlines()) == 2
    [p] = json.loads(_get(f"{url}/api/plans")[1])
    assert p["verdict"] == "fail" and p["notes"] == 1


def test_plan_is_served_under_a_locked_down_csp(base) -> None:
    url, _ = base
    [p] = json.loads(_get(f"{url}/api/plans")[1])
    with urllib.request.urlopen(f"{url}/plan/{p['plan_id']}/plan.html") as r:
        csp = r.headers["Content-Security-Policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";"))
    assert directives["connect-src"] == "'none'"  # cannot POST to /api/events
    assert "'unsafe-inline'" not in directives["script-src"]  # no injected <script>
    assert "'unsafe-eval'" not in directives["script-src"]
    # The app shell itself is not constrained this way.
    with urllib.request.urlopen(f"{url}/") as r:
        assert r.headers["Content-Security-Policy"] is None


def test_retried_event_is_acknowledged_not_duplicated(base) -> None:
    url, data = base
    [p] = json.loads(_get(f"{url}/api/plans")[1])
    ev = {"event": "note.create", "plan_id": p["plan_id"], "tab": "Plan", "quote": "retry webhooks",
          "prefix": "", "suffix": "", "text": "t", "eid": "eid-000001", "id": "note-000001"}
    assert _post(f"{url}/api/events", ev)[1]["duplicate"] is False
    assert _post(f"{url}/api/events", ev)[1]["duplicate"] is True
    assert len((data / "notes.jsonl").read_text().splitlines()) == 1


def test_bad_event_is_400_and_not_logged(base) -> None:
    url, data = base
    code, res = _post(f"{url}/api/events", {"event": "verdict", "plan_id": "000000000000", "verdict": "pass", "text": ""})
    assert code == 400 and "unknown plan" in res["error"]
    assert not (data / "notes.jsonl").exists()


def test_static_app_and_404s(base) -> None:
    url, _ = base
    assert _get(f"{url}/")[0] == "text/html"
    assert _get(f"{url}/app/app.js")[0] in ("text/javascript", "application/javascript")
    for path in ("/app/../server.py", "/plan/000000000000/plan.html", "/nope"):
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(url + path)
        assert exc.value.code == 404
