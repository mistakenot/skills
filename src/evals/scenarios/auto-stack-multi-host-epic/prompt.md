The `auto-stack/` directory holds a checkout of auto-stack, a Go monorepo of
tools for autonomous coding that ship as subcommands of one `auto` binary.
Two of them matter here:

- `auto ui` (`auto-ui/`) — a local web dashboard. It serves a no-build SPA
  over HTTP and WebSocket, and today reads planning docs straight off the
  local filesystem.
- `auto watch` (`auto-watch/`) — a per-user daemon that watches repos,
  dispatches agent tasks into tmux, and records them in SQLite.

They are joined by an event bus (`docs/auto-bus-spec.md`, `auto-shared/bus`)
that hooks post into via `auto hooks fire`, and by a project registry at
`~/.auto/projects.json`. All of it is single-host and broadcast-everything:
one machine, one user, auto-ui reading files directly.

Plan an epic for the following initiative.

Three real scenarios need multi-project and multi-host support: one developer
working across several repos on one machine; a shared dev server where each
user runs their own daemon; and a distributed setup of laptops, CI boxes and
GPU machines. Auto-ui cannot see other users' projects and cannot reach other
hosts. The direction is to invert the architecture: auto-watch becomes the
per-user authority (filesystem access, task dispatch, event production) and
auto-ui becomes a stateless proxy that connects to one or more auto-watch
backends and renders whatever they serve. From the user's seat: `auto ui
serve`, add a backend by address, open the browser, see projects from every
connected host, pick one, dispatch a task, watch its events arrive live.

Read the codebase and its docs before you plan against it. Write the epic
into `auto-stack/docs/epics/` following whatever convention the repo has.

You are running autonomously: there is no user to answer questions, so do not
stop to ask. Record anything you would have asked in the document itself and
proceed on your best judgement. Do not plan or implement any individual task;
the deliverable is the epic.
