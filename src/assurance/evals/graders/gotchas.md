# Assurance eval — known gotchas

A curated, language-agnostic list of anti-patterns the eval watches for in the
**with-skill** arm's output. Each gotcha is detected mechanically by
`cases/<case>/checks.sh` (deterministic — no LLM judgment), so rerunning the
eval N times measures the *agent's* nondeterminism, not grader noise.

Each probe is a falsifiable observation over the produced workspace. A gotcha
that fires is a **defect of the skill's output**, not of the harness.

Detection is token-based to stay language-agnostic:

- **PBT library tokens** (a real generator-based framework is present in imports
  or manifests): `hypothesis`, `fast-check`/`fast_check`, `proptest`,
  `quickcheck`, `jqwik`, `gopter`, `hedgehog`, `scalacheck`, `fscheck`,
  `cscheck`. Extend this list as new ecosystems appear.
- **Property-vocabulary tokens** (the output *claims* property/invariant
  testing): `propert`, `invariant`, `commutativ`, `idempoten`, `roundtrip` /
  `round-trip`, `forall` / `for all`.

## The gotchas

### G1 — fake PBT (`g_fake_pbt`)

The output uses property/invariant vocabulary but ships **no generator-based PBT
library**. This is the "property-style unit test" trap: asserting
`add(2,3) == add(3,2)` at a few hand-picked points and calling it
property-based testing. Real PBT generates inputs across the space.

**Fires when:** property-vocabulary tokens are present in test files **AND** no
PBT-library token is present anywhere in the workspace.

This is the gotcha the card's "Key distinction from unit testing" paragraph
exists to prevent.

### G2 — over-prescribed property layer (`g_separate_pbt_layer`)

A dedicated property-test layer (a `tests/properties/` directory or a
`verify-properties` make subtarget) was created. For a small task, properties
should live alongside unit tests under the existing subtarget; a separate layer
is over-engineering. (For larger projects this may be legitimate — interpret per
case.)

**Fires when:** a `properties`/`property` test directory exists **OR** a
`verify-properties` target appears in a Makefile.

### G3 — randomness without determinism (`g_nondeterminism_unmanaged`)

A real PBT library is present, but there is no sign of seed/determinism
management (no seed pinning, no recorded/regression seed, no derandomize
setting). Randomized tests with no reproducibility story are flaky by
construction.

**Fires when:** a PBT-library token is present **AND** no seed/determinism token
(`seed`, `derandomize`, `deterministic`, `random_state`) appears in any config,
manifest, or test file. (Reported as not-applicable when no PBT library is
present.)
