"""Arm resolution: turning an arm name into a skill directory to install.

Three forms, and the name alone decides which:

  * ``none`` — install nothing. The baseline arm: the same prompt, the same
    model, the same clean room, minus the skill.
  * ``WORKTREE`` — compile ``src/`` and copy ``skills/<name>`` off disk.
  * anything else — a git ref, materialised with ``git archive <ref> -- skills/<name>``.

``none`` and ``WORKTREE`` are therefore reserved: a branch or tag called either
one cannot be addressed as an arm.

**``WORKTREE`` is not a git operation and must not become one.** ``git archive``
can only see committed content, so a ref arm cannot evaluate an edit you have
not committed. Evaluating a change *before* committing it is the entire author
loop; ``WORKTREE`` exists precisely to reach the bytes git cannot.

Every arm carries the provenance needed to answer "what exactly did I measure?"
a day later — a resolved commit sha for a ref, and for ``WORKTREE`` the head it
sits on plus whether the tree was dirty. See `Arm.manifest`.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .paths import COMPILED_SKILLS_DIR, COMPILER, REPO_ROOT

WORKTREE = "WORKTREE"
NONE = "none"
RESERVED = (NONE, WORKTREE)

MANIFEST_NAME = "manifest.json"

# What an arm resolved to, for the manifest's `kind` field.
KIND_NONE = "none"
KIND_WORKTREE = "worktree"
KIND_REF = "ref"

# Characters allowed in the directory segment an arm writes to. A ref name may
# contain `/` (`origin/main`) which would otherwise nest run directories, and in
# the worst case `..`, which would escape the run tree entirely.
_SAFE_DIR_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


class ArmResolutionError(RuntimeError):
    """The arm could not be turned into an installable skill directory."""


@dataclass(frozen=True)
class Arm:
    """One resolved arm: what to install, and where it came from."""

    name: str
    kind: str
    skill_src: Path | None
    sha: str | None = None
    head: str | None = None
    dirty: bool | None = None

    @property
    def dir_name(self) -> str:
        """The directory segment this arm's evidence goes under."""
        return dir_name(self.name)

    def manifest(self, skill: str) -> dict:
        """The provenance record written next to the arm's cells.

        `sha` is the question a reader actually asks: for a ref it is the commit
        the skill was archived from; for `WORKTREE` it is the literal string
        `WORKTREE`, because there is no commit — `head` and `dirty` say what
        that working tree was.
        """
        return {
            "arm": self.name,
            "kind": self.kind,
            "skill": skill,
            "sha": self.sha,
            "head": self.head,
            "dirty": self.dirty,
            "source": str(self.skill_src) if self.skill_src is not None else None,
        }


def dir_name(arm: str) -> str:
    """A single, safe path segment for an arm name.

    Ref names are not path-safe: `origin/main` would nest, and `..` would climb
    out of the run tree. Anything outside the allowlist becomes `-`.
    """
    slug = "".join(c if c in _SAFE_DIR_CHARS else "-" for c in arm)
    if not slug.strip(".-"):
        raise ArmResolutionError(
            f"arm {arm!r} has no usable directory name; it would resolve to {slug!r}"
        )
    return slug


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )


def compile_skills() -> None:
    """Regenerate `skills/` from `src/`.

    `skills/` is compiled output. Without this the harness would silently
    evaluate whatever was last compiled — an edit you made a minute ago would
    not be in the arm you think you are measuring.
    """
    result = subprocess.run(
        [sys.executable, str(COMPILER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ArmResolutionError(
            "src/compile.py failed; refusing to run against a stale skills/ tree.\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )


def head_sha() -> str | None:
    """The commit `WORKTREE` sits on, or None outside a repo."""
    result = _git("rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def is_dirty() -> bool:
    """Whether the working tree differs from HEAD at all.

    Deliberately whole-tree rather than scoped to the skill: `WORKTREE` is built
    by running the compiler over `src/`, so more than `skills/<name>` feeds it.
    Over-reporting is the safe direction — it never claims a reproducibility the
    tree cannot support.
    """
    result = _git("status", "--porcelain")
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def resolve_ref(ref: str) -> str:
    """Turn a ref into the commit sha it names."""
    result = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise ArmResolutionError(
            f"arm {ref!r} is not {' or '.join(RESERVED)} and git cannot resolve it "
            f"as a commit: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _archive_skill(sha: str, skill: str) -> Path:
    """Extract `skills/<skill>` at `sha` into a fresh temp dir, and return it.

    Extracted rather than checked out: a checkout would move the working tree
    the `WORKTREE` arm is reading from, and two arms of one run must never see
    each other's state.
    """
    result = subprocess.run(
        ["git", "archive", "--format=tar", sha, "--", f"skills/{skill}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ArmResolutionError(
            f"git archive {sha[:12]} -- skills/{skill} failed; the skill may not "
            f"exist at that ref: {result.stderr.decode(errors='replace').strip()}"
        )
    dest = Path(tempfile.mkdtemp(prefix="evals-arm-"))
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        tar.extractall(dest, filter="data")
    return dest / "skills" / skill


def _require_skill_dir(skill_dir: Path, arm: str, skill: str) -> Path:
    if not (skill_dir / "SKILL.md").is_file():
        raise ArmResolutionError(
            f"arm {arm!r} has no skill {skill!r} at {skill_dir} "
            f"(expected a SKILL.md there)"
        )
    return skill_dir


def resolve(arm: str, skill: str) -> Arm:
    """Resolve one arm name into an installable `Arm`.

    Resolution is deliberately side-effect-light per arm and never touches the
    working tree, so resolving every arm up front — before the first token is
    spent — is safe and catches a typo'd ref for arm three before arm one runs.
    """
    if arm == NONE:
        return Arm(name=arm, kind=KIND_NONE, skill_src=None)

    if arm == WORKTREE:
        compile_skills()
        skill_dir = _require_skill_dir(COMPILED_SKILLS_DIR / skill, arm, skill)
        return Arm(
            name=arm,
            kind=KIND_WORKTREE,
            skill_src=skill_dir,
            sha=WORKTREE,
            head=head_sha(),
            dirty=is_dirty(),
        )

    sha = resolve_ref(arm)
    skill_dir = _require_skill_dir(_archive_skill(sha, skill), arm, skill)
    return Arm(name=arm, kind=KIND_REF, skill_src=skill_dir, sha=sha)


def resolve_all(arm_names: list[str], skill: str) -> list[Arm]:
    """Resolve every arm, rejecting anything that would share a directory.

    Two arms writing to one subtree would silently overwrite each other's
    evidence — the run would look complete and hold one arm's results twice.
    """
    seen: dict[str, str] = {}
    for name in arm_names:
        slug = dir_name(name)
        if slug in seen:
            raise ArmResolutionError(
                f"arms {seen[slug]!r} and {name!r} both write to {slug!r}; "
                f"arms must not share a directory"
            )
        seen[slug] = name
    return [resolve(name, skill) for name in arm_names]


def write_manifest(arm_dir: Path, arm: Arm, skill: str, run_id: str) -> Path:
    """Write `manifest.json` beside an arm's cells."""
    arm_dir.mkdir(parents=True, exist_ok=True)
    path = arm_dir / MANIFEST_NAME
    payload = {"run_id": run_id, **arm.manifest(skill)}
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
