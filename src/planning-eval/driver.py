"""NTM conversation driver for the planning-eval harness.  (Usage guide: see README.md)

Encapsulates the proven loop (spike S3/S4): spawn an agent in a tmux pane, send a
message, wait for the *turn* to complete (race-free: confirm GENERATING before trusting
idle), and scrape the reply text from the TUI pane.

NTM derives a session's working dir from `projects_base/<session_name>`, so the worktree
must live at `<projects_base>/<session_name>`. Callers pass a session name whose dir
already exists and is the checked-out worktree for the run.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field


class NTMError(RuntimeError):
    pass


def _ntm(args: list[str], timeout: int = 120) -> str:
    """Run an ntm command, return stdout. Raises on non-zero exit."""
    proc = subprocess.run(
        ["ntm", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise NTMError(f"ntm {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def _ntm_json(args: list[str], timeout: int = 120) -> dict:
    out = _ntm(args, timeout=timeout)
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise NTMError(f"ntm {' '.join(args)} returned non-JSON: {out[:200]}") from e


@dataclass
class Turn:
    """One agent turn: what we sent and what the agent replied (cleaned)."""

    sent: str
    reply: str
    raw_tail: str
    wall_ms: int
    state_at_end: str


@dataclass
class Session:
    """A live NTM-hosted agent we can converse with."""

    name: str
    transcript: list[Turn] = field(default_factory=list)

    # ----- lifecycle -----------------------------------------------------

    @classmethod
    def spawn(cls, name: str) -> "Session":
        """Spawn one Claude agent, no user pane, isolated of CASS/hooks noise.

        The dir `<projects_base>/<name>` must already exist (the run worktree).
        """
        _ntm(
            [
                "spawn",
                name,
                "--cc=1",
                "--no-user",
                "--no-cass-context",
                "--no-hooks",
                "--no-recovery",  # else NTM injects a "continue where you left off" prompt
            ],
            timeout=180,
        )
        s = cls(name=name)
        try:
            s._await_ready()
        except Exception:
            s.kill()  # never leave a half-spawned session orphaned
            raise
        return s

    def kill(self) -> None:
        try:
            _ntm(["kill", self.name, "--force"], timeout=60)
        except NTMError:
            pass

    # ----- state ---------------------------------------------------------

    def _agent_state(self) -> str:
        d = _ntm_json(["activity", self.name, "--json"], timeout=30)
        agents = d.get("agents", [])
        if not agents:
            return "UNKNOWN"
        return agents[0].get("state", "UNKNOWN")

    def _await_ready(self, timeout_s: int = 120) -> None:
        """Wait until the freshly-spawned agent is WAITING (ready for input).

        Claude Code shows a one-time "trust this folder?" gate the first time it runs in a
        new directory (e.g. a fresh /tmp worktree). That holds the agent in UNKNOWN, never
        WAITING, so we auto-accept it once when seen.
        """
        deadline = time.monotonic() + timeout_s
        trusted = False
        while time.monotonic() < deadline:
            if self._agent_state() == "WAITING":
                return
            if not trusted and self._trust_gate_open():
                # Option 1 = "Yes, I trust this folder"; sending "1" selects and confirms.
                _ntm_json(["--robot-send=" + self.name, "--msg=1"], timeout=30)
                trusted = True
            time.sleep(1.0)
        raise NTMError(f"agent in {self.name} never reached WAITING")

    def _trust_gate_open(self) -> bool:
        pane = self._tail(lines=30).lower()
        return "trust" in pane and "folder" in pane

    # ----- conversation --------------------------------------------------

    def send(self, message: str, turn_timeout_s: int = 600) -> Turn:
        """Send a message and block until the agent finishes its reply turn.

        Race-free turn detection (S4): after sending, first confirm the agent has
        *started* working (GENERATING/THINKING) before waiting for idle, so we never
        mistake the pre-turn idle for a completed reply.
        """
        baseline = _reply_lines(self._tail(lines=200))
        start = time.monotonic()
        _ntm_json(["--robot-send=" + self.name, "--msg=" + message], timeout=60)

        self._confirm_turn_started(timeout_s=8)
        self._wait_idle(timeout_s=turn_timeout_s)

        wall_ms = int((time.monotonic() - start) * 1000)
        raw = self._tail(lines=200)
        reply = _new_reply(baseline, raw)
        turn = Turn(
            sent=message,
            reply=reply,
            raw_tail=raw,
            wall_ms=wall_ms,
            state_at_end=self._agent_state(),
        )
        self.transcript.append(turn)
        return turn

    def _confirm_turn_started(self, timeout_s: int) -> None:
        """Poll until the agent leaves WAITING (turn began), or give up quietly.

        A very fast turn can begin and end inside the poll interval; if we never catch
        a busy state we fall through to _wait_idle, which then returns ~immediately.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._agent_state() in ("GENERATING", "THINKING"):
                return
            time.sleep(0.4)

    def _wait_idle(self, timeout_s: int) -> None:
        _ntm_json(
            ["--robot-wait=" + self.name, "--wait-until=idle", f"--timeout={timeout_s}s"],
            timeout=timeout_s + 30,
        )

    def _tail(self, lines: int) -> str:
        d = _ntm_json(["--robot-tail=" + self.name, f"--lines={lines}"], timeout=30)
        pane = d.get("panes", {}).get("0", {})
        return "\n".join(pane.get("lines", []))


def _reply_lines(raw_tail: str) -> list[str]:
    """Assistant output lines from a TUI pane. Claude marks them with a leading '●'."""
    out: list[str] = []
    for line in raw_tail.splitlines():
        stripped = line.strip()
        if stripped.startswith("●"):
            out.append(stripped.lstrip("● ").rstrip())
    return out


def _new_reply(baseline: list[str], raw_tail: str) -> str:
    """Reply text new since `baseline` — the lines this turn added to the pane (S4).

    Scrollback means we diff line *content*, not position: return the '●' lines present
    now but not in the pre-send snapshot, preserving order. Heuristic but good enough for
    the hand-scripted spine; to be hardened later.
    """
    seen = set(baseline)
    fresh = [ln for ln in _reply_lines(raw_tail) if ln not in seen]
    return "\n".join(fresh).strip()
