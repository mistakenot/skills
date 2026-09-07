"""Agent CLI contract — the flags our skills depend on, checked against reality.

The skills under ``src/planning-workflow`` (and the eval harnesses) drive
``claude``, ``codex``, ``grok`` and ``herdr`` from bash with hardcoded flags:
permission bypasses, sandbox modes, headless/print mode, pane and worktree
control. Those CLIs change fast, and when a flag is renamed or removed the
skill keeps "working" right up until a background worker stalls on a
permission prompt nobody can answer.

This module is the machinery behind ``test_agent_cli_contract.py``:

* ``load_contract``   — reads ``agent-cli-contract.toml`` (the flags we rely on).
* ``parse_help``      — turns ``<cmd> --help`` output into a flag/values table.
* ``scan_sources``    — finds every ``claude|codex|grok|herdr ...`` invocation in
                        the skill sources and extracts the flags it uses.

Run ``python agent_cli_contract.py`` to print the inventory of invocations the
scanner finds — useful when adding a new flag to the contract.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC_ROOT = REPO_ROOT / "src"
CONTRACT_PATH = HERE / "agent-cli-contract.toml"

AGENTS = ("claude", "codex", "grok", "herdr")

# --- contract ---------------------------------------------------------------


@dataclass(frozen=True)
class Command:
    """One command path in the contract, e.g. ``codex exec`` or ``herdr agent start``."""

    agent: str
    path: tuple[str, ...]  # subcommand words after the agent name
    flags: frozenset[str]
    values: dict[str, tuple[str, ...]]  # flag -> enum values that must exist

    @property
    def argv(self) -> list[str]:
        return [self.agent, *self.path]

    @property
    def key(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class Agent:
    name: str
    verified_version: str
    live_smoke: list[str] | None
    live_expect: str | None
    commands: dict[str, Command]  # keyed by Command.key


@dataclass(frozen=True)
class Contract:
    agents: dict[str, Agent]

    def command(self, agent: str, path: tuple[str, ...]) -> Command | None:
        return self.agents[agent].commands.get(" ".join((agent, *path)))

    def all_commands(self) -> list[Command]:
        return [c for a in self.agents.values() for c in a.commands.values()]


def load_contract(path: Path = CONTRACT_PATH) -> Contract:
    raw = tomllib.loads(path.read_text())
    agents: dict[str, Agent] = {}
    for name, spec in raw["agent"].items():
        commands: dict[str, Command] = {}
        for entry in spec.get("command", []):
            path_words = tuple(entry.get("path", "").split())
            cmd = Command(
                agent=name,
                path=path_words,
                flags=frozenset(entry.get("flags", [])),
                values={k: tuple(v) for k, v in entry.get("values", {}).items()},
            )
            commands[cmd.key] = cmd
        agents[name] = Agent(
            name=name,
            verified_version=spec["verified_version"],
            live_smoke=spec.get("live_smoke"),
            live_expect=spec.get("live_expect"),
            commands=commands,
        )
    return Contract(agents=agents)


# --- help parsing -----------------------------------------------------------

_OPTION_LINE = re.compile(r"^\s{2,}(-{1,2}[A-Za-z])")
_FLAG_TOKEN = re.compile(r"(?<![\w-])(-{1,2}[A-Za-z][\w-]*)")
_CLAP_VALUES = re.compile(r"\[possible values:\s*([^\]]+)\]")
_COMMANDER_CHOICES = re.compile(r"\(choices:\s*([^)]+)\)")
_QUOTED = re.compile(r'"([^"]+)"')


@dataclass
class HelpSurface:
    """Flags and enum values advertised by one ``<cmd> --help``."""

    argv: list[str]
    text: str
    flags: set[str] = field(default_factory=set)
    values: dict[str, set[str]] = field(default_factory=dict)


def parse_help(argv: list[str], text: str) -> HelpSurface:
    """Parse commander (claude) and clap (codex/grok/herdr) style help output.

    An option line is an indented line starting with ``-x`` or ``--long``. The
    option group is the text before the first run of two+ spaces (or the
    description on the next line); every ``-x``/``--long`` token in it is a
    flag. Enum values are read from the block of lines that follows the option
    line, in either clap's ``[possible values: a, b]`` or commander's
    ``(choices: "a", "b")`` form.
    """
    surface = HelpSurface(argv=argv, text=text)
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _OPTION_LINE.match(line):
            i += 1
            continue
        group = re.split(r"\s{2,}", line.strip(), maxsplit=1)[0]
        # Commander puts `<placeholder>` in the group; drop it before tokenising.
        group = re.sub(r"<[^>]*>", " ", group)
        flags = _FLAG_TOKEN.findall(group)
        # Collect the block up to the next option line for enum values.
        block = [line]
        j = i + 1
        while j < len(lines) and not _OPTION_LINE.match(lines[j]):
            block.append(lines[j])
            j += 1
        block_text = "\n".join(block)
        vals: set[str] = set()
        for m in _CLAP_VALUES.finditer(block_text):
            vals |= {v.strip() for v in m.group(1).split(",") if v.strip()}
        for m in _COMMANDER_CHOICES.finditer(block_text):
            vals |= set(_QUOTED.findall(m.group(1)))
        for f in flags:
            surface.flags.add(f)
            if vals:
                surface.values.setdefault(f, set()).update(vals)
        i = j
    return surface


def run_help(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run ``<argv> --help`` with stdin closed; returns (rc, combined output)."""
    proc = subprocess.run(
        [*argv, "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
    )
    return proc.returncode, proc.stdout + proc.stderr


_VERSION = re.compile(r"(\d+(?:\.\d+)+)")


def installed_version(agent: str, timeout: int = 30) -> str | None:
    proc = subprocess.run(
        [agent, "--version"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    m = _VERSION.search(proc.stdout + proc.stderr)
    return m.group(1) if m else None


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


# --- source scanning --------------------------------------------------------

# An agent name at a command position: not glued to a path (`/bin/claude`), a
# hyphenated name (`w-claude`), a variable (`$claude`) or another word.
_CMD_START = re.compile(r"(?<![\w/.$-])(?<!--kind )(claude|codex|grok|herdr)\b(?![\w/.-])")
_SUBCOMMAND = re.compile(r"^[a-z][a-z-]*$")
_FLAG = re.compile(r"^-{1,2}[A-Za-z][\w-]*")
# Shell filters that commonly follow a `|` — stop scanning there so `jq -r`
# flags aren't attributed to the agent.
_PIPE_FILTERS = {"jq", "grep", "rg", "tee", "head", "tail", "awk", "sed", "xargs", "sort", "wc", "cut", "tr"}
# Max depth of subcommand words we attribute to a command path.
_MAX_PATH = {"claude": 2, "codex": 2, "grok": 1, "herdr": 2}

SCAN_SUFFIXES = {".md", ".sh", ".py", ".toml", ".yaml", ".yml"}
SCAN_EXCLUDE_DIRS = {"__pycache__", ".venv", "node_modules", "runs", "cache"}


@dataclass(frozen=True)
class Invocation:
    agent: str
    path: tuple[str, ...]
    flags: tuple[str, ...]
    file: Path
    line: int
    text: str

    @property
    def key(self) -> str:
        return " ".join((self.agent, *self.path))


def _join_continuations(text: str) -> list[tuple[int, str]]:
    """Join backslash-continued lines; yields (first_line_no, joined_text)."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    for n, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip()
        if not buf:
            start = n
        if stripped.endswith("\\"):
            buf.append(stripped[:-1])
            continue
        buf.append(stripped)
        out.append((start, " ".join(buf)))
        buf = []
    if buf:
        out.append((start, " ".join(buf)))
    return out


def _tokenize(s: str) -> list[str]:
    try:
        return shlex.split(s, posix=True)
    except ValueError:
        return s.split()


def _clean(tok: str) -> str:
    return tok.strip("[]()<>`'\",;")


def parse_invocation(text: str, file: Path, line: int) -> list[Invocation]:
    """Extract agent invocations (possibly nested after ``--``) from one line."""
    if text.lstrip().startswith("#"):
        return []
    m = _CMD_START.search(text)
    if not m:
        return []
    # Cut trailing markdown/backtick and a comment.
    rest = text[m.end():]
    rest = rest.split("`", 1)[0]
    rest = re.split(r"\s#", rest, maxsplit=1)[0]
    tokens = _tokenize(rest)
    return _parse_tokens(m.group(1), tokens, file, line, text)


def _parse_tokens(agent: str, tokens: list[str], file: Path, line: int, text: str) -> list[Invocation]:
    path: list[str] = []
    flags: list[str] = []
    results: list[Invocation] = []
    kind: str | None = None  # herdr `agent start --kind X` names the nested agent
    # `<name>|--clear` style alternations in usage lines: split into parts.
    tokens = [part for tok in tokens for part in (tok.split("|") if "|" in tok and tok != "|" else [tok])]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("|", "&&", "||", ";"):
            # Stop at a pipe into a shell filter, or at any command separator.
            if tok == "|" and i + 1 < len(tokens) and tokens[i + 1] not in _PIPE_FILTERS:
                i += 1
                continue
            break
        if tok == "--":
            # Everything after `--` is the nested agent's argv. `herdr agent
            # start --kind X -- <args>` launches X itself, so the args omit the
            # executable; otherwise the first nested token names the agent.
            nested = tokens[i + 1:]
            if nested and nested[0] in AGENTS:
                results.extend(_parse_tokens(nested[0], nested[1:], file, line, text))
            elif kind in AGENTS:
                results.extend(_parse_tokens(kind, nested, file, line, text))
            break
        clean = _clean(tok)
        if _FLAG.match(clean):
            name = clean.split("=", 1)[0]
            flags.append(name)
            if name == "--kind" and i + 1 < len(tokens):
                kind = _clean(tokens[i + 1])
        elif not flags and len(path) < _MAX_PATH[agent] and _SUBCOMMAND.match(clean):
            path.append(clean)
        i += 1
    results.insert(0, Invocation(agent, tuple(path), tuple(flags), file, line, text.strip()))
    return results


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SCAN_EXCLUDE_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix in SCAN_SUFFIXES and p.resolve() != Path(__file__).resolve():
                    files.append(p)
    return sorted(files)


def scan_sources(roots: list[Path]) -> list[Invocation]:
    found: list[Invocation] = []
    for f in iter_source_files(roots):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, joined in _join_continuations(text):
            found.extend(parse_invocation(joined, f, line_no))
    return found


# Sources whose agent invocations the contract must cover. Keep this list in
# step with where skills and harnesses shell out to an agent.
DEFAULT_SCAN_ROOTS = [
    SRC_ROOT / "planning-workflow",
    SRC_ROOT / "assurance" / "evals" / "run.sh",
]


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or DEFAULT_SCAN_ROOTS
    by_cmd: dict[str, dict[str, list[Invocation]]] = {}
    for inv in scan_sources(roots):
        if not inv.flags:
            continue
        for fl in inv.flags:
            by_cmd.setdefault(inv.key, {}).setdefault(fl, []).append(inv)
    for key in sorted(by_cmd):
        print(f"== {key}")
        for fl in sorted(by_cmd[key]):
            locs = by_cmd[key][fl]
            where = ", ".join(f"{i.file.relative_to(REPO_ROOT)}:{i.line}" for i in locs[:3])
            more = f" (+{len(locs) - 3})" if len(locs) > 3 else ""
            print(f"   {fl:<45} {where}{more}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
