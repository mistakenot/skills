"""Where a fixture's repo and an arm's skills come from, when not a local path.

Two optional fixture shapes resolve through here:

  * `fixture.repo_url` (instead of `fixture.target_repo`) — any git URL. The
    one commit the fixture names is fetched, shallow, into a local cache and
    the rest of the harness treats that cache as the target repo. An open-source
    repo at the commit before an issue's fix is the intended use.

  * `arm.skills_ref` (instead of `arm.skills_dir`) — a commit-ish of *this*
    repo. Its compiled `skills/` tree is exported into the cache, so an arm is
    "the skills as they were at <sha>" and older versions can be replayed
    without checking anything out.

Both caches are keyed by immutable identity (URL + sha, skills sha), so they
never need invalidating; `rm -rf` of the cache directory is always safe.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "planning-eval-harbor"


class SourceError(ValueError):
    """A repo or skills ref cannot be resolved."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True,
    )


def repo_cache_dir(url: str, cache: Path = CACHE) -> Path:
    """The cache checkout for `url` — deterministic, filename-safe."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", url.split("://")[-1]).strip("-")
    return cache / "repos" / slug


def has_commit(repo: Path, sha: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def ensure_commit(url: str, sha: str, cache: Path = CACHE) -> Path:
    """A local repo that contains `sha` from `url`; fetched shallow on first use."""
    repo = repo_cache_dir(url, cache)
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        _git(repo, "init", "-q")
        _git(repo, "remote", "add", "origin", url)
    if not has_commit(repo, sha):
        # GitHub (and any server with uploadpack.allowReachableSHA1InWant) serves
        # a single commit by sha; depth 1 keeps a large repo to one tree.
        res = _git(repo, "fetch", "-q", "--depth", "1", "origin", sha, check=False)
        if res.returncode != 0 or not has_commit(repo, sha):
            raise SourceError(f"cannot fetch {sha} from {url}: {res.stderr.strip() or 'not found'}")
    return repo


def resolve_ref(repo_root: Path, ref: str) -> str:
    res = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    if res.returncode != 0:
        raise SourceError(f"skills ref {ref!r} is not a commit in {repo_root}")
    return res.stdout.strip()


def export_skills(repo_root: Path, ref: str, cache: Path = CACHE) -> tuple[str, Path]:
    """`(sha, dir)`: the compiled `skills/` tree of `repo_root` at `ref`."""
    sha = resolve_ref(repo_root, ref)
    dest = cache / "arms" / sha
    skills = dest / "skills"
    if skills.is_dir():
        return sha, skills
    res = subprocess.run(
        ["git", "-C", str(repo_root), "archive", "--format=tar", sha, "skills"],
        capture_output=True,
    )
    if res.returncode != 0:
        raise SourceError(f"no skills/ tree at {sha[:12]}: {res.stderr.decode().strip()}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Extract beside the destination and rename, so a crash never leaves a
    # half-written arm that a later run would trust.
    tmp = Path(tempfile.mkdtemp(dir=dest.parent, prefix=f".{sha[:12]}-"))
    try:
        with tarfile.open(fileobj=io.BytesIO(res.stdout)) as tar:
            tar.extractall(tmp, filter="data")
        tmp.rename(dest)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        if not skills.is_dir():
            raise
    return sha, skills
