---
hash: "2d22f3f0"
read_when: "designing or extending the init skill, or adding/editing a pattern or template for new-repo setup"
summary: "Draft design for an `init` skill that sets up new repos from high-level templates composed of reusable patterns (GCP/Terraform, IAM, SOPS, Neon, Trigger.dev, TS lint stack, DDD-lite, ontology), writes INIT.md for approval, implements it, then uninstalls itself."
title: "Init architectures"
---

Init architectures

- init will be a skill to set up new repos
- that pattern will be an `init` skill that contains a bunch of templates with guidance on how to set them up
- once the init is done, the skill should de-install and remove itself.
- the pattern is that the skill has a few different reference architectures. 
- the skill when run will read the reference architecture, make some tweaks based on what the user inputs, then write INIT.md, then when the user is happy proceed with settings things up.

Hosting providers:

- Typically GCP. Can include firebase stack, but most common is cloud run for hosting web apps.
- Hertzner is sometimes used

Idea: we have coarse "templates", each template is end to end description of a stack, when using a template in the skill, we show it to the user, ask them if they want any changes, before writing the init.md

NOTE: whenever you see {{ SOME_CONTENT }} it means either:
- A decision that the user needs to make, or
- Some template variable that we captured earlier.

e.g. {{ YES / NO }} means: ask the user to make a yes / no decision at this point dependent on the context around it.

## Patterns

A Pattern is a composable pattern that can be mixed with other techniques to create a full template. Composition over inheritance.

**GCP managed via Terraform**
- Terraform using Infrastructure Manager to deploy to GCP.
- Typically created in a fresh GCP project dedicated to this task.
- Bootstrapped via bash gcloud commands run by user.
- `developer` role used in local coding environment. 

**SOPS > CI secrets**
- PREREQUISITES: KMS / cloud secret manager key available to use.
- Canonical secrets file stored in repo, like `secrets.yaml` if one env, or `secrets/$ENV.yaml` if multi-environment.
- Encrypt it with the KMS system native to the cloud we're using.
- CI pipeline uses a script that reads from the file and selectively sets the deployed values in the server environment.
- Opt in, don't just copy all vars to the server.

**IAM 3x2 role pattern**
- 2x {{ GCP Projects | AWS Accounts }}, Dev / Prod.
- 3x iam roles per project (managed with terraform). roles are:
  - developer: used by ai coding tools in the reposiroty.
  - deployer: used by build pipelines to deploy everything.
  - runner: used by the cloud run app to serve traffic, access dbs, etc.
- developer role can:
  - CRUD all data in development project
  - It can read GCP infra, but can't create (terraform does this)
  - CRUD secrets in development repo / project
  - it {{ CAN/CANNOT }} read data from production db. no write to production db.
- deployer role can:
  - CRUD cloud infrastructure
  - CRUD on secrets / servers / etc
  - Cannot read from data stores, blob storage, etc.
layer:
- Terraform using Infrastructure Manager to deploy to GCP.

**Neon Postgres**
- Set up postgres in neon.tech
- Set up MCP in development environment for monitoring
- 1x db for development, 1x db for production
- Use postgres in docker for local development
- Store connection strings in secrets

**auth env worktrees**
- Pre-requisites: We are using worktrees.
- Use `auto env` to spinup / spindown worktree dev environments

**Trigger Control Plane / Web API Data plane**
- Pre-requiesites: Deploying web app with api
- Trigger.dev is the control plan for schedules crons and work queues
- But trigger.dev is just co-ordination, work happens in web api
- Trigger tasks pull / write to the web api using API key / appropriate auth
- Ideally same surface that other users user (e.g. MCP, ORPC, OPENAPI)
- This way trigger can manage what it is good at (concurrency, recovery, durable queue, etc) 
- But leave the actual valuable domain logic in the web app
- It should be a medium-hard task to rip out trigger and replace it with another control plane. A bit time consuming, but not impossible.

Example: Every day, scrape all posts for active users.
1. Trigger cron triggered every day
2. Trigger task calls `listActiveUsers()` on API
3. Trigger task then creates task queue jobs for each active user
4. For each user: sub-task calls `scrapeUserPosts(userId)` on the api, with limit on concurrency.

- API Failures that can be retried (HTTP 503, 429, etc) -> retry is handled by trigger.
- Ensure retries have max number of attempts with backoff.

Example: User action triggers long running task.
1. In web app, user presses button to run long running task
2. The web app uses trigger sdk to queue the task, and returns quickly
3. The task then follows the same pattern as the daily-scrape cron
- Web app may need the trigger SDK installing and API key added to secrets.

**Typescript Premium Lint Stack**
- Oxlint for basic linting. Oxfmt for code formatting.
- Dependency cruiser for protecting the dependency tree structure.
- knip for tidying up imports / etc. 
- husky for git hooks
- In all cases, use a sensible, widely supported set of defaults, with light customisation to suit the project.
- Expect that custom rules will be added over time as our coding agents encounter problems.
- Custom rules MUST be supported by at least basic automated tests.
- Consider using tsgo for fast, frequent typechecks (e.g. commit hooks) and full regular typescript for the full build check.
- Commit hook should run quick tests (< 10s)
- CI pipeline on main + pr branches should run full stack.
- {{ ASK USER FIRST }} Consider creating a baseline set of custom oxlint rules from https://github.com/dmmulroy/anti-slop/tree/main.

**Typescript Scripting**
- Single line scripts should be inlined in package.json. Multi line scripts should live under ./scripts in either a bash or zx mjs script.
- for multi-line scripts, use bash for simpler things (just a series of commands). Use zx mjs script for more complex scripts that have logic, conditionals, loops, etc. leave good comments in both cases.

**PNPM**
- Should be default choice for setting up packages.

**PM2 Dev Environment Runner**
- This is for simpler projects. 
- Create a `ecosystem.config.js` file, which is then run from `dev` command in `package.json`

**Docker-Compose environment runner**
- For more complex projects that might require postgres + redis + emulators, etc.

**DDD-lite**
- Depends on: `ontology` pattern.
- Use some of the basic ideas of DDD to structure our backend domain code.

What to keep from DDD:
- Pure core. Can run entirely in memory. Prefer functional code.
- Hexagonal architecture: Ports/Adapters, inbound/outbound. 
- Domain never references adapters.
- Use lint tools to enforce structural rules.
- Organise code by domain folder.
- Cross domain communication done with either Events (notify X that Y happened) or Query interfaces (following ports/adapters).
- Prefer integration tests that stub out true external dependencies / services. Use real DB as long as it runs locally.
- Unit tests can be used, but dont write tests that are coupled to implementation details.
- Aggregate roots can be used if the logic is complex enough.
- For inputs / actions, {{ ASK USER }} whether to use:
  - Use case functions, or
  - Command pattern.
- If using RBAC, permission declaration is part of the domain code.

**Ontology**
- Yaml file, `./docs/ontology.yaml`, that is `@` imported into AGENTS and CLAUDE.
- Tracks the ubiquitous language
- Should be concise. Most detail is held in code files, this is just an outline per entity, using progressive disclosure principles, like:

```yaml
entities:
  Tenant:
    description: "The per-customer boundary. One tenant per customer. Acts as container for per-client configuration and data security seperation." 
    globs: [".tenant.ts", ".tenant.tsx", "./src/domain/tenants/**/*", "docs/tenants.md"] # useGlobs: to learn more try some of these glob patterns to find related files
    greps: ["Tenant"] # Use these grep patterns to find related functionality
```

- Whole file should be no more than a few hundred lines. Other details should live in code, comments, docs, etc.

## Templates

**Advanced Typescript Web App**

Recipes used:
-
