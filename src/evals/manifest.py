"""Run-level provenance: `runs/<run-id>/manifest.json`.

One question has to stay answerable a week later: *what exactly did this run
compare?* The per-arm `manifest.json` (`arms.write_manifest`) already answers it
for a single arm — resolved sha, the head a `WORKTREE` arm sat on, whether that
tree was dirty. What it cannot answer is the run-shaped half: which arms were in
the same comparison, against which prompt, on which model, in which invoke mode,
and over how many trials.

**This file points at the per-arm records rather than copying them.** Two files
claiming the same sha is one file that can be wrong, and the one that drifts is
always the summary. `read` hydrates each arm off its own `manifest.json` at read
time, so a round trip hands back the resolved shas without a second copy of them
ever having existed on disk.

It is written the moment the run starts — before the first token is spent — and
updated when the run ends. A run killed halfway therefore still lists, still
names its arms, and is visibly `status: incomplete` rather than silently absent.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import arms as arms_mod

RUN_MANIFEST_NAME = "manifest.json"
SCHEMA = 1

# How a run ended. `incomplete` is the state a manifest is born in: it means the
# process never came back to say otherwise, which is exactly what a killed or
# crashed run should look like.
STATUS_INCOMPLETE = "incomplete"
STATUS_OK = "ok"
STATUS_FAILED = "failed"


class ManifestError(RuntimeError):
    """The run manifest is missing or unreadable."""


def now() -> str:
    """A timestamp with an offset — a run compared across machines needs one."""
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class ArmRecord:
    """One arm as the run manifest sees it, hydrated from the per-arm record.

    `name` and `dir_name` are the run manifest's own; everything below them is
    read back out of `<dir>/manifest.json` and is `None` when that file is not
    there yet (an arm the run never reached) or the run predates it.
    """

    name: str
    dir_name: str
    kind: str | None = None
    sha: str | None = None
    head: str | None = None
    dirty: bool | None = None
    source: str | None = None

    @property
    def resolved(self) -> bool:
        """Whether the per-arm record was found and read."""
        return self.kind is not None


@dataclass(frozen=True)
class RunManifest:
    """Everything needed to say what a run compared."""

    run_id: str
    skill: str | None = None
    arms: list[ArmRecord] = field(default_factory=list)
    prompt: str | None = None
    scenario: str | None = None
    model: str | None = None
    runner: str | None = None
    invoke: str | None = None
    trials: int = 1
    # Companion skills (`--with`) installed beside the skill on every arm that
    # installed it. Empty for a run without them, or one that predates them.
    with_skills: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    status: str = STATUS_INCOMPLETE
    # False for a run that predates the manifest, or one whose manifest was
    # removed: `list` still has to show it rather than pretend it is not there.
    complete_record: bool = True

    @property
    def arm_names(self) -> list[str]:
        return [a.name for a in self.arms]


def _arm_pointer(name: str, dir_name: str) -> dict:
    return {
        "arm": name,
        "dir": dir_name,
        # Relative so a run directory stays readable after it is moved or copied
        # off the machine that produced it.
        "manifest": f"{dir_name}/{arms_mod.MANIFEST_NAME}",
    }


def write(
    run_dir: Path,
    run_id: str,
    skill: str,
    arm_names: list[tuple[str, str]],
    prompt: str,
    model: str,
    runner: str,
    invoke: str,
    trials: int = 1,
    scenario: str | None = None,
    with_skills: list[str] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    status: str = STATUS_INCOMPLETE,
) -> Path:
    """Write `manifest.json` into `run_dir`. `arm_names` is (name, dir_name).

    Called twice per run: once up front with `status=incomplete`, once at the
    end with a `finished_at` and a real status. The second call rewrites the
    whole file, so the two never disagree.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "run_id": run_id,
        "skill": skill,
        "model": model,
        "runner": runner,
        "invoke": invoke,
        "trials": trials,
        "scenario": scenario,
        "with": list(with_skills or []),
        "prompt": prompt,
        "started_at": started_at or now(),
        "finished_at": finished_at,
        "status": status,
        "arms": [_arm_pointer(name, dir_name) for name, dir_name in arm_names],
    }
    path = run_dir / RUN_MANIFEST_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def read_json(path: Path) -> dict | None:
    """A JSON object from `path`, or None if it is absent or unreadable.

    A missing or half-written record is a normal state for a run that was
    killed, and reading a run directory must never be the thing that throws.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _hydrate(run_dir: Path, pointer: dict) -> ArmRecord:
    """Turn one arm pointer into a record, reading the per-arm manifest."""
    name = str(pointer.get("arm") or "")
    dir_name = str(pointer.get("dir") or name)
    rel = pointer.get("manifest") or f"{dir_name}/{arms_mod.MANIFEST_NAME}"
    per_arm = read_json(run_dir / rel) or {}
    return ArmRecord(
        name=name,
        dir_name=dir_name,
        kind=per_arm.get("kind"),
        sha=per_arm.get("sha"),
        head=per_arm.get("head"),
        dirty=per_arm.get("dirty"),
        source=per_arm.get("source"),
    )


def read(run_dir: Path) -> RunManifest:
    """Read `run_dir`'s manifest back, with each arm hydrated from its own record.

    Raises `ManifestError` when there is no manifest to read. Use `describe` for
    the tolerant version that `evals list` needs.
    """
    data = read_json(run_dir / RUN_MANIFEST_NAME)
    if data is None:
        raise ManifestError(
            f"no readable {RUN_MANIFEST_NAME} in {run_dir}; the run predates run "
            f"manifests, or it was removed"
        )
    pointers = data.get("arms")
    pointers = pointers if isinstance(pointers, list) else []
    trials = data.get("trials")
    with_skills = data.get("with")
    with_skills = [str(w) for w in with_skills] if isinstance(with_skills, list) else []
    return RunManifest(
        run_id=str(data.get("run_id") or run_dir.name),
        skill=data.get("skill"),
        arms=[_hydrate(run_dir, p) for p in pointers if isinstance(p, dict)],
        prompt=data.get("prompt"),
        scenario=data.get("scenario"),
        model=data.get("model"),
        runner=data.get("runner"),
        invoke=data.get("invoke"),
        trials=trials if isinstance(trials, int) and trials > 0 else 1,
        with_skills=with_skills,
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        status=str(data.get("status") or STATUS_INCOMPLETE),
    )


def _infer(run_dir: Path) -> RunManifest:
    """A manifest for a run that has none: arms from the directories on disk.

    A run made before manifests existed is still evidence. Listing it with what
    can be seen — its id and its arm directories — beats hiding it, and
    `complete_record=False` keeps the difference visible rather than implied.
    """
    dirs = sorted(
        p.name for p in run_dir.iterdir() if p.is_dir()
    ) if run_dir.is_dir() else []
    trials = 1
    for name in dirs:
        numbered = [p.name for p in (run_dir / name).iterdir() if p.is_dir() and p.name.isdigit()]
        trials = max(trials, len(numbered))
    return RunManifest(
        run_id=run_dir.name,
        arms=[_hydrate(run_dir, {"arm": d, "dir": d}) for d in dirs],
        trials=trials,
        complete_record=False,
    )


def describe(run_dir: Path) -> RunManifest:
    """`read`, falling back to what the directory itself shows."""
    try:
        return read(run_dir)
    except ManifestError:
        return _infer(run_dir)
