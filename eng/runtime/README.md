# Runtime behavior tests

`eng/compat/` proves ABP APIs **compile**; it can't prove they **behave** correctly at
runtime (DI wiring, interceptors, the unit of work, data filters, the
permission-definition pipeline, etc.). This project fills the gap: it boots a real
ABP application with `AbpIntegratedTest` and asserts runtime semantics.

Run it with:

```bash
dotnet test eng/runtime/AbpRuntimeTests.csproj
```

Pinned to the same stable baseline as `eng/compat/` (**ABP 10.5.0**).

## What's covered today

A representative set — not every skill, by design. The value is depth on the
mechanisms that "compile fine but run wrong":

Application-only (no database — `RuntimeTestModule`):

- **Permission-definition pipeline** — a `PermissionDefinitionProvider` actually
  runs and its permission resolves through `IPermissionDefinitionManager`.
- **Clock normalization** — `IClock.Normalize` returns a UTC-kind value under
  `AbpClockOptions.Kind = Utc`.
- **Ambient current user** — `ICurrentPrincipalAccessor.Change` flows to
  `ICurrentUser` (id + authenticated state).
- **Dynamic-proxy interception** — an interceptor registered via `OnRegistered` +
  `Interceptors.TryAdd` actually wraps the resolved service's method call.
- **Local event delivery** — `ILocalEventBus.PublishAsync` reaches a registered
  `ILocalEventHandler`.
- **Typed distributed cache round-trip** — `IDistributedCache<T>` set/get returns
  the stored item (in-memory provider).
- **`[Authorize]` pipeline** — the auto-attached authorization interceptor throws
  `AbpAuthorizationException` for a not-granted permission, and lets the call
  through under `AddAlwaysAllowAuthorization()`.
- **Validation pipeline** — an `IValidationEnabled` service throws
  `AbpValidationException` for an argument that fails a `[Required]` rule.
- **Setting default value** — `ISettingProvider.GetOrNullAsync` returns the
  `defaultValue` a `SettingDefinitionProvider` declared.
- **Object mapping** — `IObjectMapper.Map` maps through a registered AutoMapper
  `Profile`.

DB-backed over in-memory SQLite (`EfCoreTestModule`):

- **Soft-delete data filter** — a deleted entity is filtered from normal queries
  but the row remains, and reappears with `IDataFilter.Disable<ISoftDelete>()`.
- **Unit of work controls persistence** — an insert made without completing the
  UOW (and without auto-save) is never flushed to the database.
- **Multi-tenancy isolation** — a row written under one `ICurrentTenant.Change`
  tenant is invisible to another tenant's query and reappears with
  `IDataFilter.Disable<IMultiTenant>()`.
- **Repository not-found semantics** — `GetAsync` throws `EntityNotFoundException`
  for a missing id while `FindAsync` returns null.
- **Direct delete is a physical hard delete** — `DeleteDirectAsync` removes a
  soft-delete entity's row even with `IDataFilter.Disable<ISoftDelete>()` (unlike
  `DeleteAsync`), matching the provider-dependent semantic `use-abp-repositories`
  documents for EF Core / MongoDB.
- **Data-seeding pipeline** — `IDataSeeder.SeedAsync` runs a registered
  `IDataSeedContributor` and its row is persisted.
- **Entity event fires on UOW completion** — an `EntityCreatedEventData<T>` local
  handler is not invoked mid-unit-of-work but fires when the UOW completes.
- **Extra property persistence** — `SetProperty` on an entity survives a save and
  reload via `GetProperty` (the `IHasExtraProperties` JSON column).

HTTP over a real booted web app (`webapp/` SUT + `AbpWebApplicationFactoryIntegratedTest`):

- **MVC endpoint round-trip** — an anonymous request to an open endpoint returns
  `200`, and a `[Authorize]` endpoint surfaces the cookie challenge as a `302`
  (because `Client.AllowAutoRedirect` is false) — the semantics `test-mvc-razor-ui`
  documents.
- **CORS exposed headers** — a cross-origin request gets `Access-Control-Allow-Origin`
  and an `Access-Control-Expose-Headers` that includes `_AbpErrorFormat`, proving
  `WithAbpExposedHeaders()` (`configure-cors`).
- **Health endpoints** — `/health/live` returns `200`, and `/health/ready` returns
  `503` when a readiness-tagged check is unhealthy, proving the
  `AbpEndpointRouterOptions` health wiring (`configure-production-hosting`).
- **Forwarded headers** — `X-Forwarded-Proto` / `X-Forwarded-Host` restore the
  client scheme and host the app sees (`configure-production-hosting`).
- **Conventional controllers** — an `IApplicationService` with no route attribute is
  auto-exposed at `/api/app/greeting` and returns `200` (`expose-http-apis`).

## Where to grow it

Add each behind its own fixture so a failure names the mechanism, not a test soup:

- **Cache invalidation** — an entity-change event invalidates `IEntityCache`.
- **Outbox/inbox** — outgoing events persist in the same transaction; duplicate
  inbox delivery is idempotent.

> Note on UOW transaction *rollback*: the ABP EF Core test template deliberately
> disables UOW transactions for SQLite (see the `test-abp-applications` skill), so
> a true "flush-then-rollback" assertion needs the manager restored as that skill
> documents. The persistence test above avoids that by never flushing.

## What this is *not*

This does **not** measure real agent **activation** (whether Claude Code / Codex /
Cursor / Copilot load the right skill for a prompt) — that needs the actual tools
installed and is the manual step in `RELEASING.md`. This layer proves the **eight
listed fixtures** behave as asserted — not that every documented behavior across all
skills is exercised; activation proves the *routing*.
