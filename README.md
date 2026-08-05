# Skills

A collection of reusable agent skills that implement the **Portable Task Workflow** -- an AI-agent-driven feature delivery lifecycle from requirements through merged PR.

```
requirements.md -> solution.md -> context.md -> plan.md -> worktree execution -> PR -> review -> merge -> feedback
```

Planning happens on `main`. Implementation happens on feature branches in isolated git worktrees. Each stage is a discrete skill invoked via slash command.

## Available Skills

| Skill | Description |
|---|---|
| `new-task` | Create a new task folder with `requirements.md` from user input |
| `new-solution` | Write a solution design (`solution.md`) by exploring approaches and tradeoffs |
| `new-plan` | Write `context.md` and `plan.md` by gathering codebase context and breaking work into phases |
| `execute-task` | Autonomously implement a planned task end-to-end using worktree isolation |
| `delegate-task` | Dispatch task execution to an idle Claude Code pane in a tmux session |
| `executor-status-check` | Monitor all executor panes in a tmux session and report status |
| `commit-task` | Verify completeness of planning docs and commit them to main |
| `complete-task` | Finalize a feature branch and merge it to main with PR, testing, and cleanup |
| `code-review` | Perform a structured code review with severity labels |
| `review-task` | Review task planning documents and leave structured inline comments |
| `request-claude-review` | Send task planning docs to Claude Code for review, then resolve any comments |
| `request-codex-review` | Send task planning docs to Codex for review, then resolve any comments |
| `request-grok-review` | Send task planning docs to Grok for review, then resolve any comments |
| `address-feedback` | Work through open PR review threads by fixing code and resolving threads |
| `resolve-comments` | Resolve inline review comment threads in planning docs (markdown and HTML) |
| `task-feedback-analyser` | Extract recurring patterns from completed task feedback into workflow rules |
| `generate-10-ideas` | Brainstorm 10 ideas by generating 100 candidates and filtering to the top 10 |
| `revise-readme` | Update README and documentation to reflect the current state of the project |

## Installation

Skills are installed with [`auto skill`](https://github.com/mistakenot/auto). Run it from the root of the project you want the skills available in.

### First time in a project

`auto` resolves output targets from project config rather than per-command flags, so initialise once:

```sh
auto skill init --project --target claude,agents -y
```

### Install all skills (from remote)

```sh
auto skill add mistakenot/skills --skill '*'
```

### Install a single skill (from remote)

```sh
auto skill add mistakenot/skills --skill new-task
```

Both render into `.claude/skills/` and `.agents/skills/`. Re-render at any time with `auto skill sync`, and pull upstream changes with `auto skill update`.

### Install a module (bundle of related skills)

`install.sh` wraps the same commands but understands **modules**, so you can take just the planning skills rather than all of them:

```sh
./install.sh                              # everything
./install.sh --module planning-workflow   # just the planning skills
./install.sh --target claude              # .claude/skills only
```

Run `./install.sh --help` for the module list.

## Development

Files in `./skills/` are compiled output. Edit the source files in `./src/` and run the Makefile targets:

```sh
make compile   # Compile src/ -> skills/
make install   # Compile + install locally into .claude/skills/ and .agents/skills/
make lint      # Lint all skills with auto skill
make check     # Compile + lint (pre-commit check)
```
