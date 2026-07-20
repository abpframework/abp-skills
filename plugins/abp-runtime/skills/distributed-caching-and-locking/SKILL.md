---
name: distributed-caching-and-locking
description: "Typed distributed caching and cross-instance distributed locking. USE FOR: typed IDistributedCache / GetOrAddAsync (Redis-backed), IAbpDistributedLock.TryAcquireAsync, AbpDistributedCacheOptions / [CacheName]. DO NOT USE FOR: per-entity caching (cache-entities); multi-tier hybrid cache (use-hybrid-caching); events, background jobs, or workers (background-jobs-and-events); settings/features (manage-settings-and-features); data filters (apply-data-filters)."
license: MIT
---

# Distributed Caching & Locking (ABP)

Guidance for ABP's typed distributed cache and distributed lock, plus a short pointer on data filters, settings, and features. All APIs below are verified against ABP source. Inject everything via constructor.

## When to Use

- Cache typed values across app instances with `IDistributedCache<TCacheItem>` (Redis-backed).
- Use `GetOrAddAsync` to return a cached value or compute-and-store it on a miss.
- Coordinate a critical section so only one app instance runs it at a time (`IAbpDistributedLock`).

## When Not to Use

- **Publishing/handling events, deferred jobs, or recurring workers** — use the **background-jobs-and-events** skill.
- **Defining and checking settings or features in full** — use the **manage-settings-and-features** skill. The settings/features notes below are only a pointer.
- **Data-filter details beyond the brief mention** — use the **apply-data-filters** skill.

## How it works

### Typed distributed cache

`IDistributedCache<TCacheItem>` (namespace `Volo.Abp.Caching`) is a typed wrapper over `Microsoft.Extensions.Caching.Distributed.IDistributedCache`. `TCacheItem` is a serializable class (`where TCacheItem : class`); ABP handles JSON serialization, tenant-scoped keys, and a per-type cache name automatically. The default key is a `string`; a two-generic overload `IDistributedCache<TCacheItem, TCacheKey>` supports typed keys.

Define a cache item as a plain class:

```csharp
public class ProductCacheItem
{
    public string Name { get; set; }
    public decimal Price { get; set; }
}
```

Inject and use it. `GetOrAddAsync` is the go-to method — it returns the cached value or runs your factory to produce and store it:

```csharp
public class ProductAppService : ApplicationService
{
    private readonly IDistributedCache<ProductCacheItem> _cache;
    private readonly IRepository<Product, Guid> _repo;

    public ProductAppService(
        IDistributedCache<ProductCacheItem> cache,
        IRepository<Product, Guid> repo)
    {
        _cache = cache;
        _repo = repo;
    }

    public async Task<ProductCacheItem?> GetAsync(Guid id)
    {
        return await _cache.GetOrAddAsync(
            id.ToString(),
            async () =>
            {
                var product = await _repo.GetAsync(id);
                return new ProductCacheItem { Name = product.Name, Price = product.Price };
            },
            () => new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(30)
            });
    }
}
```

Verified method signatures:

```csharp
Task<TCacheItem?> GetAsync(TCacheKey key, bool? hideErrors = null,
    bool considerUow = false, CancellationToken token = default);

Task SetAsync(TCacheKey key, TCacheItem value, DistributedCacheEntryOptions? options = null,
    bool? hideErrors = null, bool considerUow = false, CancellationToken token = default);

Task<TCacheItem?> GetOrAddAsync(TCacheKey key, Func<Task<TCacheItem>> factory,
    Func<DistributedCacheEntryOptions>? optionsFactory = null, bool? hideErrors = null,
    bool considerUow = false, CancellationToken token = default);

Task RemoveAsync(TCacheKey key, bool? hideErrors = null,
    bool considerUow = false, CancellationToken token = default);

Task RefreshAsync(TCacheKey key, bool? hideErrors = null, CancellationToken token = default);
```

Notes:

- `hideErrors` defaults to the global setting (`true`): cache errors are logged, not thrown, so a Redis outage degrades to source reads rather than failing requests.
- `AbpDistributedCacheOptions` (configure in a module's `Configure<...>`) exposes `GlobalCacheEntryOptions`, `KeyPrefix`, and `HideErrors`.
- The cache name defaults to the full (namespace-qualified) type name with the `CacheItem` suffix stripped (e.g. `MyApp.Books.BookCacheItem` → `MyApp.Books.Book`); override it with `[CacheName("...")]` on the item class.

#### Redis provider

The in-memory `IDistributedCache` is per-instance and not shared. For a real distributed cache add the `Volo.Abp.Caching.StackExchangeRedis` package, depend on `AbpCachingStackExchangeRedisModule`, and set the `Redis` connection string in `appsettings.json`. The typed `IDistributedCache<T>` API stays identical.

### Distributed lock

`IAbpDistributedLock` (namespace `Volo.Abp.DistributedLocking`) coordinates a critical section across multiple app instances — only one holder at a time for a given lock name. The default implementation (`MedallionAbpDistributedLock`) wraps the Medallion DistributedLock library.

```csharp
Task<IAbpDistributedLockHandle?> TryAcquireAsync(
    string name, TimeSpan timeout = default, CancellationToken cancellationToken = default);
```

`TryAcquireAsync` returns an `IAbpDistributedLockHandle` (which is `IAsyncDisposable`) when the lock is taken, or **`null`** when it could not be acquired within `timeout` (default `0` = don't wait). Always check for null and dispose the handle with `await using`:

```csharp
public class ReportGenerator : ITransientDependency
{
    private readonly IAbpDistributedLock _distributedLock;
    public ReportGenerator(IAbpDistributedLock distributedLock) => _distributedLock = distributedLock;

    public async Task GenerateAsync()
    {
        await using (var handle = await _distributedLock.TryAcquireAsync("daily-report"))
        {
            if (handle is null)
            {
                return; // another instance holds the lock
            }

            // critical section — runs on a single instance
        }
    }
}
```

#### Provider

The base `Volo.Abp.DistributedLocking` package needs a backing synchronization provider registered in DI. A common choice is Redis via Medallion's `RedisDistributedSynchronizationProvider` (register it as `IDistributedLockProvider`); other Medallion backends (SQL Server, Azure, ZooKeeper) work too. Without a registered provider, `IAbpDistributedLock` is not functional.

### Related infrastructure (brief)

**Data filters** — `IDataFilter` (namespace `Volo.Abp.Data`) toggles global query filters like `ISoftDelete` (namespace `Volo.Abp`) and `IMultiTenant` (`Volo.Abp.MultiTenancy`) for a scope. Wrap in a `using`:

```csharp
using (_dataFilter.Disable<ISoftDelete>())
{
    var all = await _repo.GetListAsync(); // includes soft-deleted rows
}
```

**Settings** — `ISettingProvider` (namespace `Volo.Abp.Settings`) reads config-like values with provider fallback. Providers are consulted highest-to-lowest priority (user → tenant → global → configuration → default): the first provider that returns a non-null value wins. Core method is `GetOrNullAsync(name)`; extension methods add `IsTrueAsync(name)` and `GetAsync<T>(name, defaultValue)` (`where T : struct`). Declare settings by deriving from `SettingDefinitionProvider` and overriding `void Define(ISettingDefinitionContext context)`, adding `SettingDefinition` instances via `context.Add(...)`.

**Features** — `IFeatureChecker` (namespace `Volo.Abp.Features`) gates functionality per tenant/edition. Use `IsEnabledAsync(name)` for booleans and `GetOrNullAsync(name)` / `GetAsync<T>(name)` for values. Declare features by deriving from `FeatureDefinitionProvider`, overriding `void Define(IFeatureDefinitionContext context)`, calling `context.AddGroup(...)` then `group.AddFeature(name, defaultValue, ...)`.

## Validation

- Build the app; `IDistributedCache<T>` and `IAbpDistributedLock` resolve from DI once their packages/providers are wired.
- For real cross-instance caching, confirm the `Volo.Abp.Caching.StackExchangeRedis` package + `AbpCachingStackExchangeRedisModule` dependency + `Redis` connection string are in place (the in-memory cache is per-instance and won't be shared).
- For locking, confirm a backing synchronization provider (e.g. Medallion's `RedisDistributedSynchronizationProvider` registered as `IDistributedLockProvider`) is in DI — without it `IAbpDistributedLock` is not functional.
- Observe that a second instance calling `TryAcquireAsync` on the same name gets `null` while the first holds the handle.

## Common Pitfalls

- **Not checking `TryAcquireAsync` for null** — it returns `null` when the lock isn't acquired within `timeout` (default `0` = don't wait). Treat a `null` handle as "someone else holds it" and skip the critical section.
- **Forgetting `await using` on the lock handle** — the handle is `IAsyncDisposable`; dispose it to release the lock.
- **Expecting the in-memory distributed cache to be shared** — it is per-instance. Add the Redis package/module/connection string for a real distributed cache.
- **Missing the distributed-lock provider** — without a registered synchronization provider, `IAbpDistributedLock` does nothing useful.
- **Assuming cache errors throw** — `hideErrors` defaults to `true`, so a Redis outage is logged and degrades to source reads instead of failing the request.
