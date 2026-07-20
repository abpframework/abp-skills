---
name: use-hybrid-caching
description: "ABP typed hybrid cache: in-memory L1 + distributed L2 over Microsoft.Extensions.Caching.Hybrid. USE FOR: the generic IHybridCache, GetOrCreateAsync / SetAsync / RemoveAsync / RemoveManyAsync, AbpHybridCacheOptions, HybridCacheEntryOptions, stampede protection. DO NOT USE FOR: single-tier typed IDistributedCache or IAbpDistributedLock (distributed-caching-and-locking); events or background jobs (background-jobs-and-events); automatic entity caching (cache-entities)."
license: MIT
---

# Hybrid Caching (ABP)

Guidance for ABP's typed hybrid cache: a fast in-memory L1 tier backed by a distributed L2 tier, with stampede protection. All APIs below are verified against ABP source. Inject everything via constructor.

## When to Use

- Cache a typed value that is read very frequently and benefits from a local in-memory hit (L1) while sharing a distributed tier (L2) across instances. Note the L1/L2 coherence limit: a value cached in L1 on one instance is **not** actively invalidated on other instances — each instance's local copy is stale until its own L1 entry expires. A shared L2 is the source of truth on an L1 miss, not a cross-instance invalidation bus.
- Use `GetOrCreateAsync` to return a cached value or compute-and-store it on a miss, with built-in stampede protection so concurrent callers don't all run the factory.
- Tune per-type or global entry lifetimes via `AbpHybridCacheOptions` / `HybridCacheEntryOptions`.

## When Not to Use

- **Plain single-tier typed distributed caching (`IDistributedCache<T>` / `GetOrAddAsync`) or distributed locking (`IAbpDistributedLock`)** — use the **distributed-caching-and-locking** skill. If you only need one distributed tier and don't need a local in-memory copy, that abstraction is the simpler fit.
- **Publishing/handling events, deferred jobs, or recurring workers** — use the **background-jobs-and-events** skill.
- **Repository-backed automatic entity caching with automatic invalidation on update/delete** — use the **cache-entities** skill.

## How it works

`IHybridCache<TCacheItem>` and `IHybridCache<TCacheItem, TCacheKey>` (namespace `Volo.Abp.Caching.Hybrid`, package `Volo.Abp.Caching`) are typed wrappers over `Microsoft.Extensions.Caching.Hybrid.HybridCache`. `AbpCachingModule` registers `AddHybridCache()` and binds the open generics to `AbpHybridCache<>` / `AbpHybridCache<,>` by default, so nothing extra is needed to inject them. `HybridCache` keeps a fast in-memory L1 tier and, when a distributed cache (L2) is configured, reads through to L2 on an L1 miss and populates both tiers on a write — plus it protects against cache stampede so concurrent misses for the same key run the factory once. (The ABP wrapper writes with `tags: null` and adds no cross-instance L1 invalidation of its own.)

`TCacheItem` is a serializable class (`where TCacheItem : class`). ABP handles JSON serialization (via its own serializer factory), tenant-scoped key normalization, and a per-type cache name automatically. The single-generic `IHybridCache<TCacheItem>` uses a `string` key and is just `IHybridCache<TCacheItem, string>` with an extra `InternalCache` property; the two-generic `IHybridCache<TCacheItem, TCacheKey>` supports typed keys.

Define a cache item as a plain class:

```csharp
public class ProductCacheItem
{
    public string Name { get; set; }
    public decimal Price { get; set; }
}
```

Inject and use it. `GetOrCreateAsync` is the go-to method — it returns the cached value or runs your factory to produce and store it:

```csharp
public class ProductAppService : ApplicationService
{
    private readonly IHybridCache<ProductCacheItem> _cache;
    private readonly IRepository<Product, Guid> _repo;

    public ProductAppService(
        IHybridCache<ProductCacheItem> cache,
        IRepository<Product, Guid> repo)
    {
        _cache = cache;
        _repo = repo;
    }

    public async Task<ProductCacheItem?> GetAsync(Guid id)
    {
        return await _cache.GetOrCreateAsync(
            id.ToString(),
            async () =>
            {
                var product = await _repo.GetAsync(id);
                return new ProductCacheItem { Name = product.Name, Price = product.Price };
            },
            () => new HybridCacheEntryOptions
            {
                Expiration = TimeSpan.FromMinutes(30)
            });
    }
}
```

### Verified method signatures

From `IHybridCache<TCacheItem, TCacheKey>`:

```csharp
Task<TCacheItem?> GetOrCreateAsync(
    TCacheKey key,
    Func<Task<TCacheItem>> factory,
    Func<HybridCacheEntryOptions>? optionsFactory = null,
    bool? hideErrors = null,
    bool considerUow = false,
    CancellationToken token = default);

Task SetAsync(
    TCacheKey key,
    TCacheItem value,
    HybridCacheEntryOptions? options = null,
    bool? hideErrors = null,
    bool considerUow = false,
    CancellationToken token = default);

Task RemoveAsync(
    TCacheKey key,
    bool? hideErrors = null,
    bool considerUow = false,
    CancellationToken token = default);

Task RemoveManyAsync(
    IEnumerable<TCacheKey> keys,
    bool? hideErrors = null,
    bool considerUow = false,
    CancellationToken token = default);
```

Notes:

- `GetOrCreateAsync` takes an `optionsFactory` (a `Func<HybridCacheEntryOptions>`), while `SetAsync` takes an `options` value directly. They differ when omitted: `SetAsync` falls back to the cache's configured default options (`GlobalHybridCacheEntryOptions` or a matching `ConfigureCache` entry); `GetOrCreateAsync` just passes your `optionsFactory` through, so omitting it applies **no** ABP per-cache options to that call — the underlying `HybridCache` defaults apply. Pass an `optionsFactory` when you want per-call/per-cache expiration on a `GetOrCreateAsync`.
- `hideErrors` defaults to the global setting (`AbpHybridCacheOptions.HideErrors`, default `true`): when a cache error is hidden it is logged/forwarded to the exception notifier and the call **returns `null`** — it does not re-run your factory or fall back to a source read, so handle a `null` result. With `hideErrors: false` the exception propagates.
- `considerUow` (default `false`) keeps writes in the current unit of work until it completes, so the real cache is only written on UOW completion.
- `RemoveAsync` removes a single key; `RemoveManyAsync` removes a batch in one call.
- `HybridCacheEntryOptions` is the Microsoft type from `Microsoft.Extensions.Caching.Hybrid` (e.g. `Expiration`, `LocalCacheExpiration`), not an ABP type.

### Configuration — `AbpHybridCacheOptions`

Configure in a module's `Configure<AbpHybridCacheOptions>(...)`:

```csharp
Configure<AbpHybridCacheOptions>(options =>
{
    options.GlobalHybridCacheEntryOptions = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromMinutes(20)
    };

    // Per-cache-item entry options
    options.ConfigureCache<ProductCacheItem>(new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromMinutes(5)
    });
});
```

`AbpHybridCacheOptions` exposes:

- `HideErrors` (default `true`) — hide (log) or throw cache exceptions.
- `KeyPrefix` — present on the type, but **not read** by the hybrid key normalization in this ABP version. The effective key prefix comes from `AbpDistributedCacheOptions.KeyPrefix` (applied by `IDistributedCacheKeyNormalizer`); set the prefix there, not here.
- `GlobalHybridCacheEntryOptions` — default `HybridCacheEntryOptions` when no per-cache configurator matches.
- `CacheConfigurators` — the list backing the `ConfigureCache(...)` overloads (`ConfigureCache<TCacheItem>(...)`, `ConfigureCache(Type, ...)`, `ConfigureCache(string cacheName, ...)`).

The cache name defaults to the item type's **full name** (namespace-qualified) with a trailing `CacheItem` removed (`CacheNameAttribute.GetCacheName`); override it with `[CacheName("...")]` on the item class. Items marked `[IgnoreMultiTenancy]` skip tenant-scoped key normalization.

### Distributed (L2) provider

Out of the box the hybrid cache's L2 relies on the registered `IDistributedCache`, which defaults to the per-instance in-memory distributed cache. For a real shared L2 across instances, add a distributed cache provider such as `Volo.Abp.Caching.StackExchangeRedis` (depend on `AbpCachingStackExchangeRedisModule` and set the `Redis` connection string). The typed `IHybridCache<T>` API stays identical; only the L2 backing store changes.

## Validation

- Build the app; `IHybridCache<T>` and `IHybridCache<T, TKey>` resolve from DI because `AbpCachingModule` registers them by default (no extra wiring needed for the abstraction itself).
- Confirm the value type is a serializable class (`where TCacheItem : class`); the hybrid cache serializes items as JSON.
- For a real cross-instance L2, confirm a distributed cache provider (e.g. `Volo.Abp.Caching.StackExchangeRedis` + `AbpCachingStackExchangeRedisModule` + `Redis` connection string) is wired; the default in-memory L2 is per-instance and not shared.
- Observe that concurrent misses for the same key run the factory once (stampede protection) and that a warm read is served from the local L1 tier.

## Common Pitfalls

- **Reaching for hybrid cache when a single tier is enough** — if you only need a distributed cache and no local in-memory copy, use `IDistributedCache<T>` / `GetOrAddAsync` from the distributed-caching-and-locking skill instead.
- **Confusing the method name** — it is `GetOrCreateAsync` on the hybrid cache (not `GetOrAddAsync`, which belongs to `IDistributedCache<T>`).
- **Passing options the wrong way** — `GetOrCreateAsync` takes an `optionsFactory` delegate (`Func<HybridCacheEntryOptions>`), whereas `SetAsync` takes an `options` value directly.
- **Assuming cache errors throw or fall back to source** — `HideErrors` defaults to `true`, so a hidden L2 error is logged and the call returns `null` (it does not re-run the factory); handle the `null`. Set `hideErrors: false` if you want it to throw.
- **Expecting L1 to invalidate across instances** — writing/removing on one instance does not evict another instance's L1 copy; the other stays until its L1 entry expires. Keep L1 expirations short if cross-instance staleness matters.
- **Setting `AbpHybridCacheOptions.KeyPrefix` and expecting a prefix** — it isn't wired in this version; configure `AbpDistributedCacheOptions.KeyPrefix` instead.
- **Expecting the default L2 to be shared** — without a distributed provider (e.g. Redis), the L2 is the per-instance in-memory distributed cache and won't propagate across instances.
- **Using a non-serializable or non-class cache item** — `TCacheItem` must be a class ABP can serialize to JSON.
