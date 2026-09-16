"""The Claude Code agent this harness runs, in both roles.

Imported by the *Harbor* process (`agents[].import_path`), never by the CLI or
the tests: it needs `harbor` on the path, which only the module's own
environment has.

It is a thin subclass of Harbor's `claude-code` integration that closes three
gaps found while verifying the simulated-user path against Harbor 0.23.0 (see
docs/research/harbor-vs-planning-eval.md, "What had to be patched"):

1. **Auth from a credentials file, not the environment.** This harness
   authenticates Claude Code with `~/.claude/.credentials.json` (a `claude`
   login), not an API key. Harbor forwards `CLAUDE_CODE_OAUTH_TOKEN`
   into the sandbox environment, which works for a headless `claude -p` — but
   an OAuth access token expires within hours and cannot refresh without the
   file, and in a simulated-user trial it never reaches the target at all:
   Claude Code's Bash tool strips the variable from child processes, and the
   target is a child of the user agent's shell (`acpx`). Seeding the file into
   each role's `CLAUDE_CONFIG_DIR` is the recipe `docs/headless-claude-cli-evals.md`
   verified, and it makes the env variable unnecessary.

2. **Skills reach the ACP target.** Harbor registers `--skill` directories in
   `ClaudeCode.run()`, and in a simulated-user trial `run()` executes for the
   *user* agent. The target's config dir only ever receives a settings.json, so
   the arm under test was silently absent from the agent being measured.
   `acp_install` copies them in.

3. **Nothing else changes.** The scripted (multi-step) path uses `run()` and
   `resume()` exactly as upstream, with the credentials seeded first.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

CREDENTIALS = Path.home() / ".claude" / ".credentials.json"


class ClaudeCodeReplay(ClaudeCode):
    def _sessions_dir(self) -> str:
        # Upstream's CLAUDE_CONFIG_DIR for this role (`run()` and `acp_command()`
        # both derive it this way).
        return (self.environment_logs_dir / "sessions").as_posix()

    async def _seed_credentials(self, environment: BaseEnvironment) -> None:
        if not CREDENTIALS.is_file():
            raise RuntimeError(
                f"{CREDENTIALS} not found: the harness authenticates Claude Code from "
                "that file (see docs/headless-claude-cli-evals.md)"
            )
        sessions = self._sessions_dir()
        target = f"{sessions}/.credentials.json"
        await self.exec_as_agent(environment, command=f"mkdir -p {shlex.quote(sessions)}")
        await self._upload_agent_owned_file(environment, CREDENTIALS, target)
        await self.exec_as_root(environment, command=f"chmod 600 {shlex.quote(target)}")

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        await self._seed_credentials(environment)
        await super().run(instruction, environment, context)

    async def acp_install(self, environment: BaseEnvironment) -> None:
        await super().acp_install(environment)
        await self._seed_credentials(environment)
        if self.skills_dir:
            sessions = self._sessions_dir()
            await self.exec_as_agent(
                environment,
                command=(
                    f"mkdir -p {sessions}/skills && "
                    f"cp -r {shlex.quote(self.skills_dir)}/. {sessions}/skills/"
                ),
            )
