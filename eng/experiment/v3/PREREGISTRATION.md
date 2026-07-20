# v3 skill-value experiment — PRE-REGISTRATION (frozen before any run)

**Status: DRAFT for freeze.** Once frozen, nothing below changes. Anything we
learn after seeing outputs goes into a *v4* pre-registration, and must not
overwrite these specs or the results produced under them. This document exists to
remove researcher degrees of freedom (codex design-review must-fix #2).

## Estimand (what we are measuring)

> Does loading a skill raise the probability that a coding agent, on its **first
> pass**, chooses the ABP-idiomatic approach instead of a plausible-but-wrong one?

This is **first-pass trap avoidance** — NOT total skill value. Iteration cost is a
separate, later experiment (report iterations/tokens; do not merge into this).

## Three orthogonal outcomes per run (never collapsed into one)

1. `first_try_compiles` — build **once**, no agent iteration, no fixes.
2. `behavior_passes` — a frozen per-skill behavioral assertion (or `n/a` if the
   prompt is marked approach-only).
3. `approach` ∈ {idiom, trap, mixed, neither} — derived **only** from added-code
   signals by the fixed rule below. Build/behavior never feed `approach`.

Rule for `approach` (frozen): let I = any idiom signal present, T = any trap
signal present (both computed on **added code only**, comments excluded).

- I ∧ ¬T → `idiom`
- ¬I ∧ T → `trap`
- I ∧ T → `mixed`
- ¬I ∧ ¬T → `neither`

**Headline metric:** `trap_rate` = fraction of scored runs with approach ∈
{trap, mixed}, per arm, per prompt-group. Skill effect = baseline_trap_rate −
skilled_trap_rate. Also always report the full {idiom,trap,mixed,neither}
distribution — never only the pooled trap_rate.

## Generation protocol (frozen)

- **Single pass.** Agent prompt is suffixed with: "Produce the implementation in
  one pass. Do NOT build, run, test, or iterate — output the code and stop."
- Harness builds **once** afterward; no fix loop.
- Arms per prompt: `baseline`, `skilled`, plus two negative controls:
  - `irrelevant-skill` — a genuinely unrelated skill's SKILL.md is injected
    (controls for "loading any skill just makes the model more careful").
  - `ablated` — the target skill with its "Common Pitfalls" (and any explicit
    "don't do X" lines) removed (controls for "effect is extra context, not the
    specific knowledge").
- Reader: `codex gpt-5.6-sol` at medium effort for the frozen study; a weak reader
  (Haiku 4.5 if authorized, else codex low) is a **separate** replication, same
  frozen specs.

## Trap groups (reported separately, never merged)

- **in-distribution (ID):** trap taken from the skill's own "Common Pitfalls" /
  "don't" lines. Tests whether the skill's stated content is actually used.
- **transfer (TR):** a new variant of the same underlying mistake, with wording
  and structure that do **not** reuse the skill's phrasing, ideally grounded in a
  real ABP issue/support/review case. Tests generalization.

## Scorer (frozen, blinded, three-level)

- **Level 1 — deterministic regex** for pure existence of a type/call/attribute
  on added, comment-stripped code (token-boundary).
- **Level 2 — Roslyn/AST or structural check** for relationships: is a call
  inside the required scope, does hard-delete target the entity, is the seeder on
  the executed chain, is the replacement actually registered. Where a full AST is
  too heavy, use the behavioral assertion as the oracle instead and mark the
  signal `behavior-derived`.
- **Level 3 — model extractor** only for signals that cannot be formalized. If
  used: no arm/skill/run identity given, diff order randomized, answers are
  per-item present/absent/**unclear** (unclear never counts as idiom), `approach`
  derived by the fixed rule, and a stratified random sample gets two-human review
  with reported agreement.
- Comments are **never** a positive signal (strip comments before scoring).

## Analysis rules (frozen)

- 5 runs/arm/prompt is a **pilot only**, used solely to check floor/ceiling on the
  prompts; pilot numbers do **not** enter the effect estimate.
- The confirmatory run's sample size is set from the pilot by the minimum effect
  worth caring about (target: detect a 25-percentage-point trap-rate drop).
- Analysis is **stratified by prompt** (runs within a prompt are correlated; never
  pool all runs as independent). Report per-prompt distributions + trap-rate
  difference with an interval.
- A build failure is **not** auto-classified as trap; a compile pass is **not**
  auto-classified as idiom. Approach, compile, behavior stay orthogonal.

---

## Frozen per-skill specs (5 skills)

For each: trap (source, why a plausible default, why wrong in ABP, can idiom+trap
co-occur), idiom signals, trap signals, behavioral oracle, and the two frozen
prompts (ID + TR). **Prompts name no ABP API and no mechanism.**

### 1. generate-guids (approach + behavior)

- **Trap (ID):** `Guid.NewGuid()` (or `new Guid()`, DB default `NEWID()`) for a
  new entity's key. Source: skill's own guidance to use the generator.
  - *Plausible:* `Guid.NewGuid()` is the universal .NET default.
  - *Wrong in ABP:* random v4 GUIDs fragment clustered PK indexes; ABP provides
    `IGuidGenerator` (sequential/DB-friendly).
  - *Co-occur:* yes (could inject the generator yet also call `Guid.NewGuid`
    elsewhere) → `mixed`.
- **Idiom signals (L1):** injected `IGuidGenerator`; call `GuidGenerator.Create(`.
- **Trap signals (L1):** `Guid.NewGuid(` in added code.
- **Behavioral oracle:** resolve the created entity's Id source — construct the
  service with a stub `IGuidGenerator` returning a fixed GUID; assert the new
  entity's Id equals that GUID (proves it went through the generator, not
  `Guid.NewGuid`). If the agent didn't inject the generator, oracle = fail.
- **Prompt ID:** "In Acme.Fixture, add a factory method that creates a new Product
  and assigns its identifier so the rows index well in the database."
- **Prompt TR:** "In Acme.Fixture, we insert thousands of AuditEntry rows per hour
  into SQL Server and the primary-key index is fragmenting. Add a helper that
  creates an AuditEntry with an id chosen to avoid that."

### 2. handle-dates-and-time (approach + behavior)

- **Trap (ID):** `DateTime.Now` / `DateTime.UtcNow` read inline; storing/comparing
  without the framework clock. Source: skill guidance to use `IClock`.
  - *Plausible:* reading the machine clock is the default everywhere.
  - *Wrong in ABP:* bypasses `IClock`/`AbpClockOptions` (UTC vs local policy,
    testability, normalization).
  - *Co-occur:* yes → `mixed`.
- **Idiom signals (L1):** injected `IClock`; `Clock.Now`; `Clock.Normalize(`.
- **Trap signals (L1):** `DateTime.Now` / `DateTime.UtcNow` in added code.
- **Behavioral oracle:** construct the service with a stub `IClock` whose `Now`
  returns a fixed instant; call the method; assert the recorded time equals the
  stub's instant (proves it read `IClock`, not the machine clock).
- **Prompt ID:** "In Acme.Fixture, add a method that stamps a Product with the
  moment it was published, consistent no matter which server runs it."
- **Prompt TR:** "In Acme.Fixture, add a service that decides whether a coupon has
  expired; unit tests must be able to pin 'now' to a fixed value without touching
  the system clock."

### 3. register-and-replace-services (approach + behavior)

- **Trap (ID):** editing the original implementation, or `new`-ing the custom impl
  directly, or a raw `services.AddTransient<IX, Custom>()` that does not actually
  win over the module's default. Source: skill's replace-services guidance.
  - *Plausible:* "just register my class" / "just edit the class" is the obvious
    move.
  - *Wrong in ABP:* module default registrations and `ExposeServices` mean a naive
    add may not win; ABP wants `[Dependency(ReplaceServices=true)]` +
    `[ExposeServices]` (or `context.Services.Replace`).
  - *Co-occur:* yes → `mixed`.
- **Idiom signals (L1):** `ReplaceServices` / `[Dependency(ReplaceServices`;
  `ExposeServices`; `.Replace(` in module config.
- **Trap signals (L2/behavior):** the container resolves the **default**, not the
  custom, impl; or the original file was modified (diff touches the default impl).
- **Behavioral oracle (decisive):** boot a minimal ABP module that registers the
  default, apply the agent's code, resolve the interface from the container,
  assert the resolved type is the **custom** implementation.
- **Prompt ID:** "In Acme.Fixture there's a default IGreetingService. Add a custom
  version and make the app use mine instead, without changing the existing one."
- **Prompt TR:** "A module we depend on ships its own IEmailSender registered in
  its module. In Acme.Fixture, make our SmtpEmailSender the one that gets injected
  app-wide, leaving the module untouched."

### 4. seed-application-data (approach + behavior)

- **Trap (ID):** inserting default rows directly in `OnApplicationInitialization`
  / a manual `dbContext.Add` at startup, not on the framework's seed chain.
  Source: skill's data-seed guidance.
  - *Plausible:* "add rows at startup" → put it in module init.
  - *Wrong in ABP:* bypasses `IDataSeedContributor`/`IDataSeeder`
    (idempotency, tenant scoping, ordering, invoked by the seed chain).
  - *Co-occur:* yes → `mixed`.
- **Idiom signals (L1):** `IDataSeedContributor`; `DataSeedContext`; `SeedAsync(`.
- **Trap signals (L2/behavior):** rows inserted from module init / a manual add
  not reachable from the seed chain.
- **Behavioral oracle:** run the seed chain (`IDataSeeder.SeedAsync`) against an
  in-memory/sqlite store; assert the default rows exist; run it twice and assert
  no duplicates (idempotency) — a manual startup insert typically fails the
  "invoked by the seed chain" and/or idempotency check.
- **Prompt ID:** "In Acme.Fixture, make sure a default 'Sample' Product exists the
  first time the app runs."
- **Prompt TR:** "In Acme.Fixture, a fresh deployment must come up with three
  built-in Category rows already present, and redeploys must not duplicate them."

### 5. apply-data-filters (approach + behavior; heavier oracle)

- **Trap (ID):** a hand-rolled `IsDeleted` bool + manual `.Where(x => !x.IsDeleted)`
  everywhere, or EF `IgnoreQueryFilters()` used ad hoc, instead of ABP soft-delete
  - `IDataFilter` disable-scope + `HardDeleteAsync`. Source: skill's data-filter
  guidance.
  - *Plausible:* a bool flag + manual filtering is the textbook DIY soft delete.
  - *Wrong in ABP:* reinvents `ISoftDelete`/`IDataFilter`; loses the global
    filter, the scoped disable, and repository `HardDeleteAsync`.
  - *Co-occur:* yes → `mixed`.
- **Idiom signals (L1):** `IDataFilter`; `ISoftDelete`; `HardDeleteAsync(`;
  `DisableFilter(`.
- **Trap signals (L1/L2):** a new `IsDeleted`/`Deleted` property added by the
  agent; manual `IgnoreQueryFilters(`; manual `.Where(... !`IsDeleted`)`.
- **Behavioral oracle:** with an EF/sqlite context, soft-delete a row; assert a
  normal query hides it; assert that within a filter-disable scope it is visible;
  assert hard-delete removes it from the store. Mark `approach-only` if the oracle
  can't be built reliably for a given output.
- **Prompt ID:** "In Acme.Fixture, add an admin action that lists Products a user
  previously removed, and another that erases one permanently."
- **Prompt TR:** "In Acme.Fixture, 'deleting' an Order must keep it recoverable and
  hidden from normal listings, but a compliance job must be able to both see all
  removed Orders and wipe specific ones for good."

---

## What this study can and cannot conclude (frozen)

- **Can:** whether these skills reduce first-pass trap rate on these frozen
  prompts, split by ID vs TR, with compile/behavior/approach separated, and
  whether the effect survives the two negative controls.
- **Cannot:** total skill value, routing/activation value, value on unlisted
  tasks, or value for readers/effort levels not run. Those are separate studies.
