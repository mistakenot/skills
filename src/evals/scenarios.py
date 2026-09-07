"""Scenarios: the task being measured, and the workspace it needs.

A scenario is a directory, deliberately the same shape as
`src/assurance/evals/cases/` minus the grader files:

    scenarios/<name>/
        prompt.md    required — the prompt handed to every arm
        setup.sh     optional — prepares the workspace (fetches a pinned repo)
        fixture/     optional — static files copied into the workspace

`--prompt "..."` stays as the inline shorthand for throwaways; it is the same
`Scenario` with no root, no setup and no fixture.

**setup.sh runs once per scenario, not once per cell.** Running a real fetch
per arm per trial is the difference between a four-cell run costing one fetch
and costing four, and it is also a source of drift: four fetches are four
chances to disagree. So the prepared tree is built once under `cache/`, and each
cell is seeded by copying it. The consequence is a constraint on setup.sh: it
must produce a *relocatable* tree, because the directory it runs in is not the
directory the agent will see. No absolute paths baked into generated files.

**Pinning is checked, not trusted.** `check_pins` fails a setup.sh that names a
branch anywhere a ref is expected, and fails one that fetches remote content
without a literal 40-character sha. Two reasons it is a hard check rather than a
review note: a floating fixture drifts under you between runs, so two runs a week
apart are not comparable; and for a "plan how to add feature X" task, if X was
merged upstream in the meantime, a floating fetch hands the agent the answer and
the eval measures nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import MODULE_DIR

SCENARIOS_DIR = MODULE_DIR / "scenarios"
CACHE_DIR = MODULE_DIR / "cache"

PROMPT_NAME = "prompt.md"
SETUP_NAME = "setup.sh"
FIXTURE_NAME = "fixture"

# Inside a cache entry: the prepared tree that is copied per cell, and the
# marker recording that the fetch already happened. The marker is a *sibling*
# of the payload, never inside it — it is harness bookkeeping and must not
# appear in the workspace the agent sees.
PAYLOAD_NAME = "ws"
MARKER_NAME = "FETCHED"

INLINE_NAME = "inline"

SETUP_TIMEOUT = 600


class ScenarioError(RuntimeError):
    """The scenario directory is not usable."""


class PinError(ScenarioError):
    """A setup.sh names a floating ref, or fetches without pinning one."""


class SetupError(ScenarioError):
    """The scenario's setup.sh failed."""


@dataclass(frozen=True)
class Scenario:
    """One task: a prompt, and optionally the workspace it needs prepared."""

    name: str
    prompt: str
    root: Path | None = None
    setup: Path | None = None
    fixture: Path | None = None

    @property
    def needs_preparation(self) -> bool:
        return self.setup is not None


# --- loading ---------------------------------------------------------------


def inline(prompt: str) -> Scenario:
    """The `--prompt "..."` shorthand: a prompt and nothing else."""
    return Scenario(name=INLINE_NAME, prompt=prompt)


def available() -> list[str]:
    """The bundled scenario names. The catalog is `ls scenarios/`."""
    if not SCENARIOS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in SCENARIOS_DIR.iterdir()
        if p.is_dir() and (p / PROMPT_NAME).is_file()
    )


def resolve(name_or_path: str) -> Scenario:
    """Load a scenario by bundled name or by path.

    A bare name is looked up under `scenarios/` first, so the common case is
    `--scenario datasette-parquet-renderer` rather than a path into the module.
    """
    candidate = SCENARIOS_DIR / name_or_path
    if os.sep not in name_or_path and candidate.is_dir():
        return load(candidate)
    return load(Path(name_or_path))


def load(root: Path) -> Scenario:
    """Read and validate a scenario directory.

    Everything that can be checked without running anything is checked here —
    including the pin check — so a malformed scenario fails before an arm is
    compiled, let alone before a token is spent.
    """
    root = Path(root)
    if not root.is_dir():
        known = ", ".join(available()) or "(none bundled)"
        raise ScenarioError(f"no scenario directory at {root}; bundled: {known}")

    prompt_path = root / PROMPT_NAME
    if not prompt_path.is_file():
        raise ScenarioError(
            f"scenario {root} has no {PROMPT_NAME}; it is the one required file"
        )
    prompt = prompt_path.read_text().strip()
    if not prompt:
        raise ScenarioError(f"scenario {root}: {PROMPT_NAME} is empty")

    setup = root / SETUP_NAME
    setup = setup if setup.is_file() else None
    if setup is not None:
        check_pins(setup.read_text(), where=setup)

    fixture = root / FIXTURE_NAME
    fixture = fixture if fixture.is_dir() else None

    if setup is None and fixture is None and not prompt:
        raise ScenarioError(f"scenario {root} is empty")

    return Scenario(
        name=root.name, prompt=prompt, root=root, setup=setup, fixture=fixture
    )


# --- the pin check ---------------------------------------------------------

_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
_SHA_ANYWHERE = re.compile(r"(?<![0-9a-zA-Z])[0-9a-f]{40}(?![0-9a-zA-Z])")

# Does this script reach off the machine at all? A purely local setup.sh
# (mkdir, write files, install from a vendored tree) has no ref to pin, and
# demanding a sha from it would be noise.
_FETCHES = re.compile(r"\b(?:git\s+clone|git\s+fetch|curl|wget|codeload|https?://)")

# `NAME=value`, optionally behind export/readonly/local. The natural way to
# write a pinned setup.sh is a `SHA=` at the top and `$SHA` below, so refs are
# expanded through these before being judged.
_ASSIGN = re.compile(
    r"^[ \t]*(?:export[ \t]+|readonly[ \t]+|local[ \t]+)*"
    r"([A-Za-z_][A-Za-z0-9_]*)=(.*?)[ \t]*$",
    re.MULTILINE,
)

# A ref sitting in a GitHub-style archive URL: `/tar.gz/<ref>`,
# `/archive/<ref>.tar.gz`, `/zipball/<ref>`.
_ARCHIVE_URL = re.compile(
    r"/(?:tar\.gz|tarball|zipball|archive)/(?P<ref>[^\s;&|'\"]+)"
)

_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".zip")

# Subcommands whose positional argument is a ref we must see pinned.
_CHECKOUT_LIKE = ("checkout", "switch", "reset")


def _strip_comments(text: str) -> str:
    """Drop `#` comments so prose about a branch cannot fail the check."""
    out = []
    for line in text.splitlines():
        in_single = in_double = False
        cut = None
        for i, ch in enumerate(line):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                # `#` mid-word (a URL fragment, `foo#bar`) is not a comment.
                if i == 0 or line[i - 1].isspace():
                    cut = i
                    break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def _assignments(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, raw in _ASSIGN.findall(text):
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        values[name] = raw
    return values


def _expand(ref: str, values: dict[str, str]) -> str:
    """Expand `$VAR` / `${VAR}` against the script's own assignments."""
    def sub(match: re.Match) -> str:
        name = match.group(1) or match.group(2)
        return values.get(name, match.group(0))

    for _ in range(4):  # assignments may reference each other
        expanded = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", sub, ref)
        if expanded == ref:
            break
        ref = expanded
    return ref.strip("\"'")


def _commands(text: str) -> list[list[str]]:
    """Split into simple commands and tokenize each, best effort."""
    commands = []
    for line in text.splitlines():
        for part in re.split(r"&&|\|\||[;|]", line):
            part = part.strip()
            if not part or part.startswith("#!"):
                continue
            try:
                tokens = shlex.split(part, posix=True)
            except ValueError:
                tokens = part.split()
            if tokens:
                commands.append(tokens)
    return commands


def _git_refs(commands: list[list[str]]) -> list[tuple[str, str]]:
    """Every ref a git command in the script names, with the site that named it."""
    found: list[tuple[str, str]] = []
    for tokens in commands:
        if Path(tokens[0]).name != "git":
            continue
        rest = tokens[1:]
        # Skip git's own global flags (`-C dir`, `--no-pager`).
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        if not rest:
            continue
        sub, args = rest[0], rest[1:]

        for i, arg in enumerate(args):
            if arg in ("-b", "--branch") and i + 1 < len(args):
                found.append((f"git {sub} {arg}", args[i + 1]))
            elif arg.startswith("--branch="):
                found.append((f"git {sub} --branch", arg.split("=", 1)[1]))

        positional = [a for a in args if not a.startswith("-")]
        if sub in _CHECKOUT_LIKE and positional:
            found.append((f"git {sub}", positional[-1]))
        elif sub == "fetch" and len(positional) >= 2:
            # `git fetch <remote> <ref>` — the shallow-clone-a-branch idiom.
            found.append(("git fetch", positional[-1]))
    return found


def _url_refs(text: str) -> list[tuple[str, str]]:
    found = []
    for match in _ARCHIVE_URL.finditer(text):
        ref = match.group("ref")
        for suffix in _ARCHIVE_SUFFIXES:
            if ref.endswith(suffix):
                ref = ref[: -len(suffix)]
                break
        found.append(("archive url", ref))
    return found


def check_pins(script: str, where: Path | str = SETUP_NAME) -> None:
    """Fail a setup.sh that floats.

    Two rules:

      * every ref the script names — `git checkout`, `--branch`, an archive
        URL's last segment — must be a literal 40-character sha, after
        expanding the script's own variables;
      * a script that fetches anything remote must carry at least one such sha,
        so a bare `git clone` with no checkout cannot slip through by naming no
        ref at all.

    Raises `PinError` naming the offending ref. This is a check rather than a
    convention because review does not reliably catch a branch name that reads
    perfectly well.
    """
    body = _strip_comments(script)
    values = _assignments(body)

    sites = _git_refs(_commands(body)) + _url_refs(body)
    for site, raw in sites:
        ref = _expand(raw, values)
        if _SHA.match(ref):
            continue
        detail = f"{raw!r}" if ref == raw else f"{raw!r} (expands to {ref!r})"
        raise PinError(
            f"{where}: {site} names {detail}, which is not a 40-character sha. "
            f"Scenario fixtures must be pinned: a floating ref drifts between "
            f"runs, and for a 'plan how to add X' task it can hand the agent an "
            f"upstream X that did not exist when the scenario was written."
        )

    if _FETCHES.search(body) and not _SHA_ANYWHERE.search(body):
        raise PinError(
            f"{where}: fetches remote content but carries no 40-character sha. "
            f"Pin the fixture to a commit."
        )


# --- the clone cache -------------------------------------------------------


def _digest_tree(root: Path) -> str:
    """A content hash of a directory: same bytes and layout, same digest."""
    sha = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            sha.update(b"d\0" + rel.encode())
        elif path.is_file():
            sha.update(b"f\0" + rel.encode() + b"\0")
            sha.update(hashlib.sha256(path.read_bytes()).digest())
    return sha.hexdigest()


def cache_key(scenario: Scenario) -> str:
    """What makes two prepared workspaces the same one.

    The setup script's bytes plus the fixture's contents. Both are pinned by
    construction — the script to a sha, the fixture to whatever is committed —
    so the same key really is the same tree, and editing either one produces a
    new entry rather than silently reusing a stale one.
    """
    sha = hashlib.sha256()
    sha.update(scenario.setup.read_bytes() if scenario.setup else b"")
    sha.update(b"\0")
    sha.update((_digest_tree(scenario.fixture) if scenario.fixture else "").encode())
    return sha.hexdigest()[:16]


def entry_dir(scenario: Scenario, cache_dir: Path | None = None) -> Path:
    """Where this scenario's prepared workspace lives.

    Named `<scenario>-<key>` so `ls cache/` is readable, keyed so an edit to
    setup.sh or the fixture lands in a new entry.
    """
    root = CACHE_DIR if cache_dir is None else Path(cache_dir)
    return root / f"{scenario.name}-{cache_key(scenario)}"


def _run_setup(scenario: Scenario, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    if scenario.fixture is not None:
        shutil.copytree(scenario.fixture, workspace, dirs_exist_ok=True)
    result = subprocess.run(
        ["bash", str(scenario.setup)],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=SETUP_TIMEOUT,
    )
    if result.returncode != 0:
        raise SetupError(
            f"scenario {scenario.name}: {SETUP_NAME} exited {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )


def prepare(scenario: Scenario, cache_dir: Path | None = None) -> Path | None:
    """The directory whose contents seed every cell's workspace.

    No setup.sh: the fixture directory itself (or None — a prompt-only
    scenario needs no seeding). With a setup.sh: a cached prepared tree, built
    on first use and reused thereafter, so a four-cell run fetches once.

    The cache entry is assembled under a private temp name and moved into place
    in one `rename`, so a half-fetched tree is never visible as a cache hit — an
    interrupted first run leaves nothing to reuse rather than something broken.
    """
    if not scenario.needs_preparation:
        return scenario.fixture

    entry = entry_dir(scenario, cache_dir)
    payload = entry / PAYLOAD_NAME
    if (entry / MARKER_NAME).is_file() and payload.is_dir():
        return payload

    entry.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{scenario.name}-", dir=entry.parent))
    try:
        _run_setup(scenario, staging / PAYLOAD_NAME)
        # The marker is written before the entry is published, so its presence
        # is what makes the entry a hit. Never rewritten on reuse: a test can
        # assert on its mtime and contents to prove no second fetch happened.
        (staging / MARKER_NAME).write_text(
            json.dumps(
                {
                    "scenario": scenario.name,
                    "key": cache_key(scenario),
                    "setup": str(scenario.setup),
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                },
                indent=2,
            )
            + "\n"
        )
        try:
            os.rename(staging, entry)
        except OSError:
            # Another process published the same entry while we were fetching.
            # Theirs is as good as ours by construction — the key is a content
            # hash — so discard ours rather than clobbering a tree that a cell
            # may already be copying from.
            shutil.rmtree(staging, ignore_errors=True)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if not payload.is_dir():
        raise SetupError(
            f"scenario {scenario.name}: {SETUP_NAME} left no workspace at {payload}"
        )
    return payload
