---
name: configure-audit-logging
description: "ABP audit logging: per-request log of requests, actions, entity change history, exceptions. USE FOR: enabling/disabling auditing, GET request logging, entity change history, AuditLogContributors, ignoring types, [Audited]/[DisableAuditing], manual scopes with IAuditingManager. DO NOT USE FOR: general application/UI logging or Serilog (configure-logging); setting/feature values (manage-settings-and-features); background jobs/workers/handlers (background-jobs-and-events)."
license: MIT
---

# Configuring Audit Logging in ABP

ABP automatically creates one **audit log object** per web request. It records request/response details, executed actions (controller/app-service calls with parameters), entity changes, exceptions, and duration. Startup templates already add the `UseAuditing()` middleware and wire the Audit Logging module (which implements `IAuditingStore` to save to a database). Without a store, `SimpleLogAuditingStore` just writes to the standard logger.

## When to Use

- Enabling or disabling auditing globally via `AbpAuditingOptions`.
- Auditing GET/HEAD requests, which are skipped by default.
- Selecting which entities record change history (selectors or `[Audited]`/`[DisableAuditing]`).
- Turning auditing off for a specific controller/app-service, or opting a non-controller class in.
- Adding an `AuditLogContributor` to enrich the log.
- Creating manual audit scopes with `IAuditingManager`.

## When Not to Use

- **General application or UI logging / Serilog configuration** — use the configure-logging skill instead.
- **Tracking setting or feature values** — use the manage-settings-and-features skill instead.
- **Authoring background jobs, workers, or event handlers** — use the background-jobs-and-events skill for that; auditing the code they run stays here (e.g. an `IAuditingManager` scope).

## How it works

### AbpAuditingOptions

Configure in your module's `ConfigureServices`:

```csharp
Configure<AbpAuditingOptions>(options =>
{
    options.IsEnabled = true;
    options.IsEnabledForGetRequests = false;
});
```

Key options (verified against `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Auditing/Volo/Abp/Auditing/AbpAuditingOptions.cs`):

- `IsEnabled` (default `true`): master switch. When false, nothing else applies.
- `HideErrors` (default `true`): swallow + log errors that occur while saving the audit log instead of throwing. Set false if audit persistence is critical.
- `IsEnabledForAnonymousUsers` (default `true`): set false to log only authenticated users.
- `AlwaysLogOnException` (default `true`): on an exception, force the log to be saved, taking priority over the write filters (`IsEnabledForAnonymousUsers`, `IsEnabledForGetRequests`). It does **not** override the earlier scope exclusions — an ignored URL (`IgnoredUrls`) or an integration-service request (when `IsEnabledForIntegrationServices` is false) is skipped before the audit scope is even created, so it's never logged even on exception.
- `IsEnabledForIntegrationServices` (default `false`): enable auditing for integration services.
- `IsEnabledForGetRequests` (default `false`): safe methods (GET, HEAD) are skipped by default; set true to also audit them.
- `DisableLogActionInfo` (default `false`): stop logging `AuditLogActionInfo` entries.
- `SaveEntityHistoryWhenNavigationChanges` (default `true`): also record entity changes when a navigation property changes.
- `ApplicationName`: distinguishes logs when multiple apps share one database (falls back to `IApplicationInfoAccessor.ApplicationName`).
- `IgnoredTypes` (`List<Type>`): types fully ignored — as entities their changes aren't saved, and they're skipped when serializing action parameters. Defaults already include `Stream`, `Expression`, `CancellationToken`.
- `Contributors` (`List<AuditLogContributor>`): extension points, see below.
- `EntityHistorySelectors` (`IEntityHistorySelectorList`): choose which entities record change history, see below.
- `AlwaysLogSelectors`: selectors forcing the log to be saved when matched.

There is a separate `AbpAspNetCoreAuditingOptions.IgnoredUrls` (prefix list) for ignoring URLs, and `AbpAspNetCoreAuditingUrlOptions` (`IncludeSchema`/`IncludeHost`/`IncludeQuery`, all default false) to control what the logged URL contains.

### Entity change history

Entity change history is **off by default** — no entity changes are saved unless you opt an entity in, to avoid huge databases. Two ways to opt in:

**1. Selectors** (dynamic, by predicate):

```csharp
Configure<AbpAuditingOptions>(options =>
{
    options.EntityHistorySelectors.AddAllEntities(); // log every entity

    // or a custom predicate:
    options.EntityHistorySelectors.Add(
        new NamedTypeSelector(
            "MySelectorName",
            type => typeof(IEntity).IsAssignableFrom(type)));
});
```

**2. `[Audited]` / `[DisableAuditing]` attributes** (per entity / property):

```csharp
[Audited]
public class MyUser : Entity<Guid>
{
    public string Name { get; set; }
    public string Email { get; set; }

    [DisableAuditing] // never record this property's changes
    public string Password { get; set; }
}
```

Inverse pattern — mark the entity `[DisableAuditing]` and opt in only chosen properties with `[Audited]`. `[DisableAuditing]` on a property also accepts `UpdateModificationProps` (default `true`) and `PublishEntityEvent` (default `true`) — set false to skip touching `LastModificationTime` / suppress `EntityUpdatedEvent` (EF Core only).

An entity is skipped for change logging if it's in `IgnoredTypes`, isn't an `IEntity`, or its type isn't public.

### Enabling/disabling per service

Controller actions and application-service methods are audited by default. Use `[DisableAuditing]` on a class or method to turn it off:

```csharp
public class HomeController : AbpController
{
    [DisableAuditing]
    public async Task<ActionResult> Home() { return View(await GetModelAsync()); }
}
```

For **other** (non-controller/non-app-service) classes, audit logging is off by default. Opt in with `[Audited]` on the class/method, or implement `IAuditingEnabled`.

### Contributors

Extend the log by deriving from `AuditLogContributor` (`PreContribute` / `PostContribute`) and adding it to `Contributors`:

```csharp
public class MyAuditLogContributor : AuditLogContributor
{
    public override void PreContribute(AuditLogContributionContext context)
    {
        var currentUser = context.ServiceProvider.GetRequiredService<ICurrentUser>();
        context.AuditInfo.SetProperty("MyCustomClaimValue",
            currentUser.FindClaimValue("MyCustomClaim"));
    }
}

// registration
Configure<AbpAuditingOptions>(o => o.Contributors.Add(new MyAuditLogContributor()));
```

### Manual audit scopes with IAuditingManager

`IAuditingManager` exposes `Current` (`IAuditLogScope?`) and `BeginScope()` (returns `IAuditLogSaveHandle : IDisposable` with `SaveAsync()`).

Access the current scope from anywhere (always null-check — an outer scope may or may not exist):

```csharp
var scope = _auditingManager.Current;
if (scope != null)
{
    scope.Log.Comments.Add("Executed MyService.DoItAsync");
    scope.Log.SetProperty("MyCustomProperty", 42);
}
```

Create a scope manually (rare — normally the middleware does this per request):

```csharp
using (var auditingScope = _auditingManager.BeginScope())
{
    try
    {
        // call services; entity changes and actions accumulate into one log
    }
    catch (Exception ex)
    {
        _auditingManager.Current.Log.Exceptions.Add(ex);
        throw;
    }
    finally
    {
        await auditingScope.SaveAsync(); // always save
    }
}
```

## Validation

- Confirm `UseAuditing()` middleware is present and an `IAuditingStore` is registered — otherwise `SimpleLogAuditingStore` only writes to the logger and nothing is persisted.
- Trigger a request and verify an audit log row is created; toggle `IsEnabledForGetRequests` and confirm GET requests start/stop being recorded.
- After opting an entity in (selector or `[Audited]`), update it and verify entity change history is saved; a property marked `[DisableAuditing]` should not appear.
- Verify a manual scope persists by confirming `SaveAsync()` runs in the `finally` block.

## Common Pitfalls

- **Entity change logging is EF Core only** — the MongoDB provider does not support entity change history (other auditing features still work).
- Entity change history is **off by default**; if you expect change history and see none, you haven't opted the entity in via a selector or `[Audited]`.
- `AlwaysLogOnException` forces a save past the write filters, but it does **not** resurrect logs excluded earlier: an `IgnoredUrls` match or an integration-service request (when `IsEnabledForIntegrationServices` is false) is skipped before the scope exists, so it's never logged even on exception.
- Non-controller / non-app-service classes are **not** audited by default — opt in with `[Audited]` or `IAuditingEnabled`.
- Always null-check `IAuditingManager.Current`; an outer scope may not exist.
