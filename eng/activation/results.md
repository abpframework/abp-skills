# Activation matrix — results

Recorded runs of the `probes.yaml` set against the real tools. Procedure and the
results template are in `README.md`. Two of the four tools are automated here
(Claude Code, Codex — both CLI); Cursor and VS Code stay manual (GUI) and are not
yet recorded.

## Method

- Probes: all 158 in `probes.yaml` (79 positive `activate` + 79 anti-trigger
  `not-activate`), generated from `tests/**/eval.yaml`.
- Profile: **Everything** — all 15 plugins / 79 skills installed. This is the
  stress case (largest menu); it surfaces truncation/ordering and cross-plugin
  hand-off that a single-plugin install can't.
- Source: the **local working tree** (`Directory` marketplace), so the run reflects
  the current, uncommitted skill descriptions — same content for both tools.
- Observation is automated (no human reading an indicator):
  - **Claude Code** (`run_claude_probes.py`): reads the first `Skill` tool_use in
    `claude -p --output-format stream-json`; `--max-turns 2` bounds each probe to the
    routing decision. A probe that loads no skill records `activated = none`.
  - **Codex** (`run_codex_probes.py`): streams `codex exec --json` and stops at the
    first `command_execution` that reads `.../skills/<skill>/SKILL.md` (Codex loads a
    skill by cat-ing its `SKILL.md`); a watchdog kills the process at 90 s.
- Pass rule: `activate` passes iff the expected skill is selected; `not-activate`
  passes iff the expected skill is **not** selected (routing to a sibling or handling
  generically both pass).

## Claude Code 2.1.205 — profile: Everything (15 plugins / 79 skills) — ref: local working tree @ a2f6cb3 — date: 2026-07-17

- Discovery: 15 plugins installed, all skills listed.
- Positive probes: **71/79** selected the expected skill (concurrent run, `--jobs 3`).
- Anti-trigger probes: **75/79** correctly did NOT select the skill — of those, **70
  routed to a real sibling skill** (unambiguously correct routing) and 5 loaded no
  skill. After the anti-trigger fixes below (3 probes re-run), **78/79** — the only
  remaining miss is `handle-dates-and-time`.
- Concurrency reconciliation: 7 of the 8 positive misses were `activated = none`.
  Re-running those 7 serially (`--jobs 1`, no rate contention) flipped **2 to pass**
  (`handle-validation-and-errors`, `configure-dynamic-claims` — they had been throttled
  mid-run), leaving **5 stable non-activations**. Reconciled positive ≈ **73/79**.
- Stable non-activations (model answered without loading a skill), by shape:
  - explain / lookup prompts — `configure-multi-tenancy` ("Explain the difference…"),
    `use-abp-standard-endpoints` ("which endpoint returns…"). Captured stream shows the
    model answering from its own knowledge (it even tried to grep ABP source) instead
    of loading the skill.
  - well-known one-file patterns — `configure-logging` (Serilog bootstrap),
    `define-application-modules` (module `DependsOn`), `extend-application-shell`
    (layout head/toolbar hook). The model writes these from training without the skill.
- Positive sibling route (not a miss, a related-skill choice): `angular-ui` →
  `abp-angular-proxy`.
- Anti-trigger misfires (loaded the expected skill instead of routing away):
  `handle-dates-and-time`, `serialize-json`, `extend-objects-with-extra-properties`,
  `menus-and-localization`.
- Upgrade/uninstall: `claude plugin marketplace add/update` + `install` behaved; the
  local `Directory` source picks up working-tree edits without a re-fetch.
- Notes: Claude Code loads a skill only when it judges it needs one, so skill loading
  competes with the model's own competence — it is deliberately conservative on
  explain-shaped and well-known-pattern prompts. No truncation notice at this menu size.

## Codex codex-cli 0.144.5 (gpt-5.6-sol, low effort) — profile: Everything (15 plugins / 79 skills) — ref: local working tree @ a2f6cb3 — date: 2026-07-17

- Discovery: 15 plugins installed, all enabled.
- Positive probes: **78/79** selected the expected skill.
- Anti-trigger probes: **75/79** correctly did NOT select the skill — **all 75 routed
  to a real sibling skill** (clean routing), 0 loaded nothing. After the anti-trigger
  fixes below, **77/79** at the Everything profile — remaining misses are
  `manipulate-images` and `menus-and-localization` (the latter only under Everything;
  it routes to `angular-ui` once the menu is small enough to keep full descriptions —
  see the follow-up).
- Positive sibling route (the single positive miss): `customize-application-modules` →
  `extend-objects-with-extra-properties`.
- Anti-trigger misfires (loaded the expected skill instead of routing away):
  `manipulate-images`, `serialize-json`, `extend-objects-with-extra-properties`,
  `menus-and-localization`.
- **Menu truncation**: with all 79 skills installed Codex emits
  *"Skill descriptions were shortened to fit the 2% skills context budget. Codex can
  still see every skill, but some descriptions are shorter."* Routing stayed strong
  anyway, but a smaller profile (Backend core / one plugin) keeps full descriptions —
  a reason to prefer per-area installs over Everything.
- Upgrade/uninstall: `codex plugin marketplace remove` then `add <local path>` +
  `plugin add` behaved.
- Notes: Codex always loads a skill (reads its `SKILL.md`) before answering, so it
  always commits to a route — near-perfect positive activation, and its anti-trigger
  misses are it loading the *expected* skill rather than the sibling (never a
  "no skill" outcome). Opposite disposition from Claude Code.

## Cross-tool findings

- **Both tools agree the routing is strong**: positive activation 73–78/79, and on the
  anti-triggers the dominant behavior is *routing to the correct sibling* (Claude 70,
  Codex 75 of 79), not "load nothing" — which is the outcome the sibling `USE FOR:` /
  `DO NOT USE FOR:` markers are designed to produce.
- **Three anti-triggers misfired on both tools** — `serialize-json`,
  `extend-objects-with-extra-properties`, `menus-and-localization`. When two
  independent routers both pull the expected skill on its own anti-trigger prompt, the
  probe is borderline: the prompt sits inside the skill's real scope, or the sibling
  boundary is fuzzy. All three were diagnosed and fixed — see the follow-up below.
- **Tool dispositions differ**: Claude Code is conservative (loads a skill only when it
  judges one is needed → some explain/well-known prompts get answered directly); Codex
  is eager (always loads a skill first). Neither is wrong, but a skill whose value is in
  code output should keep its `USE FOR:` triggers concrete and task-shaped so Claude
  Code loads it, while keeping `DO NOT USE FOR:` sharp so Codex routes cleanly.
- **Everything-profile truncation is Codex-specific** at this menu size; Claude Code
  showed no truncation notice. Both are reasons the README recommends installing by
  profile rather than all 15.

## Follow-up: the three shared anti-trigger misfires — diagnosed and fixed

Each was verified against ABP source / the sibling descriptions before changing, then
the changed probe was re-run on both tools.

- **`serialize-json`** — old anti-trigger routed "change MVC JSON response formatting"
  away from the skill, but ABP's MVC JSON lives in ASP.NET Core `JsonOptions` (via
  `AddAbpJson`, `MvcCoreBuilderExtensions.cs`) which **no skill owns**, so the router
  had nowhere better to go and grabbed the only JSON skill. Retargeted the anti-trigger
  to a real named sibling from the skill's own `DO NOT USE FOR:` — encrypting a
  serialized value → `encrypt-strings` (kept the MVC scenario as an answer-shape eval).
- **`extend-objects-with-extra-properties`** — old anti-trigger ("add an extra property
  to the Identity module's user") sits in *both* skills: `customize-application-modules`
  literally lists "adding extra entity/DTO properties" in its `USE FOR:`, so the API
  overlaps. Retargeted to a customize-only task with no overlap — replacing a pre-built
  module service (`IdentityUserManager` subclass).
- **`menus-and-localization`** — the description already excludes Angular routes
  (`… Angular routes and the abpLocalization pipe (use angular-ui)`); the old prompt was
  just dense with menu/localization keywords that overpowered it. Rewrote the prompt to
  lead with the Angular `RoutesService` wiring and drop the `::Menu:Books` menu-item
  framing.

Re-run of the three fixed anti-triggers (should route to the sibling, i.e. NOT the
expected skill):

| probe | Claude Code | Codex (Everything) | Codex (abp-ui only) |
| --- | --- | --- | --- |
| `serialize-json` | pass → `encrypt-strings` | pass → `encrypt-strings` | — |
| `extend-objects-with-extra-properties` | pass → `customize-application-modules` | pass → `register-and-replace-services` | — |
| `menus-and-localization` | pass → (no skill) | **fail → `menus-and-localization`** | pass → `angular-ui` |

The one residual — Codex still grabbing `menus-and-localization` at the Everything
profile — is the **description-truncation** effect, not a probe defect: shrink Codex to
just `abp-ui` (small menu, full descriptions) and the same probe routes cleanly to
`angular-ui`. It's another data point for installing by profile rather than all 15.

Probes regenerated (`generate_probes.py`); `validate_evals.py` green (215 scenarios,
79/79 coverage).

## Not yet recorded

- **Cursor** and **VS Code / Copilot** — GUI tools, manual observation; not covered by
  the current run. Same probe set applies.
- **Smaller profiles** (single plugin, Backend core / Full-stack / Microservices) — only
  Everything was run here. Worth a pass to confirm full-description routing (esp. Codex,
  which truncates at Everything) and to exercise cross-plugin hand-off to an
  *uninstalled* plugin.

Raw per-probe results: `claude-probes.json`, `codex-probes.json` — the initial full run
(before the three anti-trigger fixes above); regenerate with the two driver scripts.
