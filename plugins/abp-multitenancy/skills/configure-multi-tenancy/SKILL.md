---
name: configure-multi-tenancy
description: >
  Configure ABP multi-tenancy with explicit host/tenant boundaries, tenant-aware entities and request resolution, and cross-tenant background execution.
  USE FOR: implementing IMultiTenant; using ICurrentTenant.Change safely; distinguishing host rows from all-tenant queries; carrying TenantId into background jobs; iterating tenants in background workers with an isolated unit of work; and understanding how entering a tenant scope drives connection resolution.
  DO NOT USE FOR: general data-filter implementation (use apply-data-filters); configuring connection strings — global, module, mapped, or per-tenant — and the full resolution/fallback order (use configure-connection-strings); general background job, worker, or event-bus setup (use background-jobs-and-events); or tenant-scoped permission definitions (use permissions-and-authorization).
license: MIT
---

# Configure ABP Multi-Tenancy

## When to Use

- Define entities that belong to the host or a tenant.
- Resolve the current tenant for an HTTP request.
- Run host-only work or act on behalf of one tenant.
- Queue a background job for a specific tenant.
- Iterate tenants from a periodic worker without sharing a unit of work across tenants.
- Understand why a tenant scope resolves to a specific (shared / per-tenant / hybrid) database — configuring the connection strings themselves is **configure-connection-strings**.

## When Not to Use

- Use **apply-data-filters** for custom filters, soft delete, and provider-specific filter implementation.
- Use **configure-connection-strings** for global named connection strings, database mappings, and `[ConnectionStringName]`.
- Use **background-jobs-and-events** to select a background provider, define retries, or register workers and event handlers.
- Use **permissions-and-authorization** for `MultiTenancySides` on permissions and authorization checks.

## How it works

### 1. Model the host/tenant boundary

`IMultiTenant` has one nullable property:

```csharp
public interface IMultiTenant
{
    Guid? TenantId { get; }
}
```

`TenantId == null` means host-owned data. A non-null value means data owned by that tenant.

```csharp
public class Product : AggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; protected set; }
    public string Name { get; private set; }

    private Product()
    {
        Name = string.Empty;
    }

    public Product(Guid id, string name)
        : base(id)
    {
        Name = name;
    }
}
```

The base `Entity` constructor calls `EntityHelper.TrySetTenantId`. For an `IMultiTenant` entity, that helper reads the ambient tenant and tries to set `TenantId`. Construct the entity inside the intended tenant scope. If host ownership is invalid for the entity, enforce the non-null invariant in the entity constructor.

EF Core adds a global filter for every `IMultiTenant` entity. While the filter is enabled, the predicate compares the entity's `TenantId` with `ICurrentTenant.Id`.

These operations are different:

- `CurrentTenant.Change(null)` enters the host context; the enabled filter returns host rows (`TenantId == null`).
- `CurrentTenant.Change(tenantId)` enters one tenant context; the enabled filter returns that tenant's rows.
- `_dataFilter.Disable<IMultiTenant>()` removes the tenant predicate; in a shared database it can return host rows and rows from every tenant.

Disabling the filter is not a way to enter the host side. It also cannot query databases that are not connected to the current unit of work.

### 2. Read and change the current tenant

`ICurrentTenant` exposes the complete context API:

```csharp
public interface ICurrentTenant
{
    bool IsAvailable { get; }
    Guid? Id { get; }
    string? Name { get; }
    IDisposable Change(Guid? id, string? name = null);
}
```

`IsAvailable` is true when `Id` has a value. `GetId()` returns the non-null id or throws `AbpException`; `GetMultiTenancySide()` maps a non-null id to `Tenant` and null to `Host`.

Always scope `Change` with `using`. It stores the parent context and restores it when disposed, including nested changes:

```csharp
public async Task<long> GetProductCountAsync(Guid tenantId)
{
    using (CurrentTenant.Change(tenantId))
    {
        return await _productRepository.GetCountAsync();
    }
}
```

Changing `ICurrentTenant` changes routing context; it does not authorize the caller. Keep host-only entry points protected by host-side permissions or equivalent authorization.

### 3. Resolve tenants for HTTP requests

Enable framework multi-tenancy explicitly when the application does not already do so:

```csharp
Configure<AbpMultiTenancyOptions>(options =>
{
    options.IsEnabled = true;
});
```

The framework option defaults are `IsEnabled = false`, `DatabaseStyle = Hybrid`, and `UserSharingStrategy = Isolated`.

Default resolvers run in this order:

1. `CurrentUserTenantResolveContributor`
2. `QueryStringTenantResolveContributor`
3. `RouteTenantResolveContributor`
4. `HeaderTenantResolveContributor`
5. `CookieTenantResolveContributor`

The current-user contributor is inserted first; the resolver stops at the first resolved tenant or host. Keep it first so an authenticated user's tenant claim is not replaced by request input.

Query string, route, header, and cookie contributors use `AbpAspNetCoreMultiTenancyOptions.TenantKey`, whose default is `"__tenant"`. Add a domain resolver in the Web/API layer:

```csharp
Configure<AbpTenantResolveOptions>(options =>
{
    options.AddDomainTenantResolver("{0}.mydomain.com");
});
```

`{0}` captures the tenant name. Add custom contributors to `AbpTenantResolveOptions.TenantResolvers`. `FallbackTenant` is used only after no contributor resolves a tenant; because it forces a tenant when resolution is empty, do not configure it when requests must still reach the host side.

The multi-tenancy middleware obtains the tenant configuration, enters `_currentTenant.Change(tenant?.Id, tenant?.Name)`, invokes the remaining pipeline, and then leaves the scope. Place `UseMultiTenancy()` after authentication so the current-user contributor can read authenticated claims.

### 4. Run one background job for one tenant

Make job arguments implement `IMultiTenant` when the job must execute for a known tenant:

```csharp
public class RebuildCatalogArgs : IMultiTenant
{
    public Guid? TenantId { get; set; }
    public Guid CatalogId { get; set; }
}

public class RebuildCatalogJob : AsyncBackgroundJob<RebuildCatalogArgs>
{
    private readonly ICatalogRebuilder _catalogRebuilder;

    public RebuildCatalogJob(ICatalogRebuilder catalogRebuilder)
    {
        _catalogRebuilder = catalogRebuilder;
    }

    public override Task ExecuteAsync(RebuildCatalogArgs args)
    {
        return _catalogRebuilder.RebuildAsync(args.CatalogId);
    }
}
```

Enqueue the tenant id as job data:

```csharp
await _backgroundJobManager.EnqueueAsync(
    new RebuildCatalogArgs
    {
        TenantId = CurrentTenant.Id,
        CatalogId = catalogId
    });
```

`BackgroundJobExecuter` detects `IMultiTenant` arguments and wraps job invocation in `CurrentTenant.Change(args.TenantId)`. A null `TenantId` therefore executes in the host context. The job implementation does not need a second tenant change.

If the argument type does not implement `IMultiTenant`, the executer uses the tenant context that exists when the job is executed. Do not rely on enqueue-time ambient context being preserved; serialize the target `TenantId` in the arguments.

### 5. Iterate tenants in a background worker

`AsyncPeriodicBackgroundWorkerBase` creates one service scope per timer tick and passes only that `ServiceProvider` and a cancellation token to `DoWorkAsync`. It does not infer or loop tenant contexts.

List tenants, enter each tenant explicitly, and begin a new unit of work for each tenant. Resolve database-bound processing from that new unit of work's service provider:

```csharp
public class CatalogMaintenanceWorker : AsyncPeriodicBackgroundWorkerBase
{
    public CatalogMaintenanceWorker(
        AbpAsyncTimer timer,
        IServiceScopeFactory serviceScopeFactory)
        : base(timer, serviceScopeFactory)
    {
        Timer.Period = 60_000;
    }

    protected override async Task DoWorkAsync(
        PeriodicBackgroundWorkerContext workerContext)
    {
        var tenantStore = workerContext.ServiceProvider
            .GetRequiredService<ITenantStore>();
        var currentTenant = workerContext.ServiceProvider
            .GetRequiredService<ICurrentTenant>();
        var unitOfWorkManager = workerContext.ServiceProvider
            .GetRequiredService<IUnitOfWorkManager>();

        var tenants = await tenantStore.GetListAsync(includeDetails: true);

        foreach (var tenant in tenants)
        {
            workerContext.CancellationToken.ThrowIfCancellationRequested();

            if (!tenant.IsActive)
            {
                continue;
            }

            using (currentTenant.Change(tenant.Id, tenant.Name))
            using (var unitOfWork = unitOfWorkManager.Begin(requiresNew: true))
            {
                var processor = unitOfWork.ServiceProvider
                    .GetRequiredService<ICatalogMaintenanceService>();

                await processor.RunAsync(workerContext.CancellationToken);
                await unitOfWork.CompleteAsync(workerContext.CancellationToken);
            }
        }
    }
}
```

`requiresNew: true` creates a new ABP unit of work and DI scope. Enter the tenant before beginning that unit of work. This keeps tenant-specific DbContexts and connection resolution inside the correct tenant boundary.

To include host work, run a separate `CurrentTenant.Change(null)` scope with its own new unit of work. Do not disable `IMultiTenant` and treat the result as equivalent to per-tenant iteration: that only spans rows in one connected shared database.

### 6. Tenant scope is what triggers a per-tenant database

`MultiTenantConnectionStringResolver` replaces `DefaultConnectionStringResolver` and checks `ICurrentTenant.Id` on every `ResolveAsync` call — so **entering a tenant scope is what makes that tenant's database take effect**. With no current tenant, a missing tenant, or a tenant that defines no connection strings, it delegates to the global resolver.

That is the only part multi-tenancy owns. **Configuring** the actual global, module, mapped, and per-tenant connection strings — and the full tenant→global resolution/fallback order — belongs to **configure-connection-strings**.

The routing switch is the current tenant:

```csharp
using (CurrentTenant.Change(tenantId))
using (var unitOfWork = UnitOfWorkManager.Begin(requiresNew: true))
{
    var repository = unitOfWork.ServiceProvider
        .GetRequiredService<IRepository<Product, Guid>>();

    await repository.GetListAsync();
    await unitOfWork.CompleteAsync();
}
```

`ITenantStore` supplies `TenantConfiguration`, including `Id`, `Name`, `NormalizedName`, `IsActive`, `EditionId`, and `ConnectionStrings`. Its interface is:

```csharp
public interface ITenantStore
{
    Task<TenantConfiguration?> FindAsync(string normalizedName);
    Task<TenantConfiguration?> FindAsync(Guid id);
    Task<IReadOnlyList<TenantConfiguration>> GetListAsync(bool includeDetails = false);

    [Obsolete("Use FindAsync method.")]
    TenantConfiguration? Find(string normalizedName);

    [Obsolete("Use FindAsync method.")]
    TenantConfiguration? Find(Guid id);
}
```

Use the async methods. A custom implementation still has to implement the obsolete synchronous members because they remain in the interface.

ABP supports separate tenant databases. The built-in Tenant Management UI does not manage tenant connection strings; implement that management surface yourself, or use a module that provides it. The configuration-backed `DefaultTenantStore` can also provide a tenant `ConnectionStrings.Default` entry.

## Validation

1. Confirm the application configures `AbpMultiTenancyOptions.IsEnabled = true`.
2. Create host, tenant A, and tenant B rows. Under the enabled filter, verify each `CurrentTenant.Change` scope returns only its own rows.
3. Disable `IMultiTenant` only against a shared database and verify that it returns rows across sides in that database.
4. Enqueue a job whose arguments implement `IMultiTenant`; assert `ICurrentTenant.Id` inside the job equals the serialized `TenantId`, including null for a host job.
5. In a periodic worker, assert every tenant iteration starts a new unit of work after entering the tenant scope.
6. Configure one tenant with a separate `Default` connection string and one without it. Resolve inside separate tenant/UOW scopes and verify the first uses its tenant database while the second falls back to the global connection.
7. Run the relevant application tests, then run the repository's skill validator.

## Common Pitfalls

- **Confusing host context with all tenants.** Host is `CurrentTenant.Id == null` with the filter still enabled; disabling the filter is a cross-side shared-database query.
- **Treating `CurrentTenant.Change` as authorization.** It changes ambient routing context only; protect who may initiate host or cross-tenant work.
- **Constructing an entity before switching tenants.** The base entity constructor captures the ambient tenant when it tries to set `TenantId`.
- **Omitting `IMultiTenant` from job arguments.** The target tenant is then not carried as job data for `BackgroundJobExecuter` to restore.
- **Changing tenant inside one reused unit of work.** Enter the tenant first and create a new UOW/service scope per tenant.
- **Using `Disable<IMultiTenant>()` with separate databases.** One query cannot span databases that are reached through different connection strings.
- **Assuming every named database mapping is available to tenants.** Tenant mapped-database fallback requires `IsUsedByTenants = true`.
- **Expecting the Tenant Management UI to edit tenant connection strings.** The framework routing exists, but that UI capability is not in the built-in module.
