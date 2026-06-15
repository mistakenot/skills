---
name: pd-test
description: "Run browser-based regression tests for pd-components. Opens HTML test fixtures in Chrome via agent-browser, executes playbook steps, and reports pass/fail. Use when 'test pd-components', 'run pd tests', 'pd-test', or after changing pd-components source."
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*), Read
---

# pd-components browser test runner

Run regression tests for the pd-components web component library using
agent-browser to drive real Chrome against HTML test fixtures.

## How it works

Each test is a pair:
- **Fixture** (`fixtures/*.html`) — minimal HTML page exercising one component or behavior.
- **Playbook** (`playbooks/*.md`) — step-by-step agent-browser commands with expected outcomes.

Fixtures load `../../dist/pd.min.js` via relative path from `file://` URLs,
so no dev server is needed.

## Process

### Step 1: Build pd-components

Ensure the dist is current before testing:

```bash
cd /home/vscode/src/skills/pd-components && npm run build
```

### Step 2: Run each playbook

Set the fixtures path:

```
FIXTURES=/home/vscode/src/skills/pd-components/tests/fixtures
```

For each `.md` file in `playbooks/`:

1. Read the playbook file.
2. Open the fixture in agent-browser.
3. Execute each `agent-browser` command in the code blocks.
4. After each command with an **expect:** annotation, compare the actual
   result to the expected value.
5. Record pass/fail per assertion.

### Step 3: Report results

Print a summary table:

```
PLAYBOOK                 PASS  FAIL  RESULT
md-dedent                  7     0   ✓ PASS
md-script-wrapper          6     0   ✓ PASS
comment-workflow          12     0   ✓ PASS
─────────────────────────────────────────
TOTAL                     25     0   ALL PASS
```

If any assertion fails, print the failing step with actual vs expected values.

### Step 4: Clean up

```bash
agent-browser close --all
```

## Important notes

- Always `wait` after opening a fixture — `<md>` elements fetch marked.js from CDN.
- The `$FIXTURES` variable in playbooks must be expanded to the absolute path.
- `agent-browser eval` returns the JS expression result as text — compare as strings.
- If clipboard operations fail in headless mode, that's expected — the test
  verifies the *store cleared* side effect, not the clipboard write.
- Screenshot each fixture after completion if you want visual confirmation:
  `agent-browser screenshot $FIXTURES/../results/<name>.png`
