# epic-backbone

Exercises the epic-altitude components: `pd-guardrail`, `pd-task` + derived
`pd-breakdown`, the derived `pd-outcome` scan/coverage strip, and the id-keyed
`pd:epic-selected` cross-highlight.

Fixture: `fixtures/epic-backbone.html` — 2 journeys (J1 journey, J2 cli), 3 guard
rails (G1/G3 functional, G2 non-functional), 3 tasks (T1→T2→T3). G3 is honored by
no task on purpose, to prove coverage-gap detection.

## Steps

1. Open the fixture, wait for components to mount.
2. **pd-outcome** derives the scan strip:
   - `journeys` tile = 2; `guard rails` tile = 3, sub "2 functional · 1 non-functional".
   - `tasks` tile = 3, sub includes "2 deployable".
   - `coverage gap` tile = 1, sub "1 rail unguarded" (G3 honored by no task).
3. **pd-guardrail** renders its head: G2 kind badge = "performance", metric chip contains "p99".
4. **pd-task** renders chips: T1 has a `deployable` chip.
5. **pd-breakdown** derives a 3-node DAG from `depends-on` (T1→T2→T3).
6. **Cross-highlight (guard rail → blast radius):** click G1. Tasks that honor it
   (T1, T3) get `.pd-epic-hl`; T2 (doesn't honor G1) does not.
7. **Cross-highlight (task → journey):** click T1. The journey it delivers (J1)
   gets `.pd-epic-hl`.

## Expected

All assertions in `run.sh` under `── epic-backbone ──` pass: derived counts and
gap detection are correct, and selection propagates both directions across the
id-keyed graph.
