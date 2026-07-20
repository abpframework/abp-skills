---
name: cache-entities
description: "Read-only single-entity-by-id caching via the generic IEntityCache abstraction (cache to the entity or a DTO), auto-invalidated. USE FOR: AddEntityCache, caching to entity or DTO, batch lookups (FindMany/GetMany), expiration, EntityCacheWithObjectMapper mapping. DO NOT USE FOR: general key/value caching or distributed locks (distributed-caching-and-locking); querying/persisting entities (ef-core-integration or mongodb-integration)."
license: MIT
---

# Cache Entities with IEntityCache

`IEntityCache<TEntityCacheItem, TKey>` is ABP's higher-level abstraction on top of the [distributed cache](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/fundamentals/caching.md). Unlike a raw `IDistributedCache<T>` where you manage keys and invalidation yourself, an entity cache knows how to load an entity from its repository, cache it, and **automatically invalidate the cached copy when the entity is updated or deleted** — so the next call re-reads from the database and re-caches.

Source: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Ddd.Domain/Volo/Abp/Domain/Entities/Caching/IEntityCache.cs` and `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Ddd.Domain/Volo/Abp/Domain/Entities/Caching/EntityCacheServiceCollectionExtensions.cs`.

## When to Use

- You repeatedly look up the same entity by id (e.g. a `Product` referenced from many places) and want caching without hand-writing cache keys or invalidation logic.
- You want caching to invalidate itself automatically when the entity is updated or deleted.
- You want to cache a leaner DTO shape instead of the entity object.
- You need batched, cache-aware lookups by a set of ids.

## When Not to Use

- **General key/value caching where you manage the key yourself** — use the distributed-caching-and-locking skill (`IDistributedCache<T>`).
- **Distributed locking** — use the distributed-caching-and-locking skill.
- **Querying or persisting entities** — use the ef-core-integration or mongodb-integration skills; the entity cache is read-only.

## How it works

### Register it

Call `AddEntityCache` in your module's `ConfigureServices`. The two-generic form caches the entity object directly (the entity must be JSON-serializable):

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddEntityCache<Product, Guid>();
}
```

Registration constraints (from the source): `TEntity : Entity<TKey>` and `TKey : notnull`.

Then inject `IEntityCache<Product, Guid>` and read:

```csharp
public class ProductAppService : ApplicationService, IProductAppService
{
    private readonly IEntityCache<Product, Guid> _productCache;

    public ProductAppService(IEntityCache<Product, Guid> productCache)
        => _productCache = productCache;

    public async Task<ProductDto> GetAsync(Guid id)
    {
        var product = await _productCache.GetAsync(id);   // DB first call, cache afterwards
        return ObjectMapper.Map<Product, ProductDto>(product);
    }
}
```

Internally the entity cache stores each item in an `IDistributedCache<EntityCacheItemWrapper<TEntityCacheItem>, TKey>`, so the cache name defaults to the full type name of `EntityCacheItemWrapper<TEntityCacheItem>` (e.g. `Volo.Abp.Domain.Entities.Caching.EntityCacheItemWrapper\`1[[...Product...]]`), not the name of`Product` or `ProductDto`. Because the resolved cache-item type is the wrapper, a`[CacheName]` attribute placed on `Product` or the cached DTO does **not** change this cache name.

### The IEntityCache interface

From `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Ddd.Domain/Volo/Abp/Domain/Entities/Caching/IEntityCache.cs` — note the generic is `<TEntityCacheItem, TKey>`, i.e. the type you inject is the **cached item type**, not necessarily the entity:

```csharp
public interface IEntityCache<TEntityCacheItem, TKey>
    where TEntityCacheItem : class
    where TKey : notnull
{
    Task<TEntityCacheItem?> FindAsync(TKey id);                                   // null if missing
    Task<List<TEntityCacheItem?>> FindManyAsync(IEnumerable<TKey> ids);           // order preserved
    Task<Dictionary<TKey, TEntityCacheItem?>> FindManyAsDictionaryAsync(IEnumerable<TKey> ids);

    Task<TEntityCacheItem> GetAsync(TKey id);                                     // throws if missing
    Task<List<TEntityCacheItem>> GetManyAsync(IEnumerable<TKey> ids);
    Task<Dictionary<TKey, TEntityCacheItem>> GetManyAsDictionaryAsync(IEnumerable<TKey> ids);
}
```

- `FindAsync` returns `null` when the entity is not found; `GetAsync` throws `EntityNotFoundException`.
- The `*Many*` methods batch-fetch only the cache-missed ids from the database, so prefer them over calling `FindAsync`/`GetAsync` in a loop.

### Cache to a DTO instead of the entity

If the entity isn't JSON-serializable, or you'd rather cache a leaner shape, register the three-generic form. ABP performs the object mapping from entity to cache item for you:

```csharp
context.Services.AddEntityCache<Product, ProductDto, Guid>();
```

You must configure the `Product -> ProductDto` mapping (AutoMapper, Mapperly, etc.):

```csharp
public class MyMapperProfile : Profile
{
    public MyMapperProfile() => CreateMap<Product, ProductDto>();
}
```

Now inject `IEntityCache<ProductDto, Guid>` — `GetAsync` returns the DTO directly:

```csharp
public class ProductAppService : ApplicationService, IProductAppService
{
    private readonly IEntityCache<ProductDto, Guid> _productCache;

    public ProductAppService(IEntityCache<ProductDto, Guid> productCache)
        => _productCache = productCache;

    public Task<ProductDto> GetAsync(Guid id) => _productCache.GetAsync(id);
}
```

### Configure expiration

Every `AddEntityCache` overload takes an optional `DistributedCacheEntryOptions`:

```csharp
context.Services.AddEntityCache<Product, ProductDto, Guid>(
    new DistributedCacheEntryOptions
    {
        SlidingExpiration = TimeSpan.FromMinutes(30)
    });
```

The default is a **2-minute** `AbsoluteExpirationRelativeToNow`.

### Custom mapping

For full control over how an entity becomes a cache item, derive from `EntityCacheWithObjectMapper<TEntity, TCacheItem, TKey>`, override `MapToValue`, and register with `ReplaceEntityCache<TCache, TEntity, TCacheItem, TKey>(...)`.

## Validation

- After registering, inject the correct cache-item type: `IEntityCache<Product, Guid>` for the two-generic form, `IEntityCache<ProductDto, Guid>` for the DTO form. A wrong generic won't resolve.
- Confirm caching: the first `GetAsync(id)` reads from the DB, subsequent calls read from cache.
- Confirm automatic invalidation: update or delete the entity through the repository, then re-read — the value should reflect the change without a manual cache clear.
- For the DTO form, confirm the `Product -> ProductDto` mapping is configured, or mapping will fail.

## Common Pitfalls

- **Read-only.** Never mutate an object obtained from the entity cache and expect it to persist. To update, read the entity through the repository, change it, and save via the repository — the cache invalidates itself on that change.
- The generic you inject is the **cache item type**. With the two-generic registration that's the entity (`IEntityCache<Product, Guid>`); with the DTO registration it's the DTO (`IEntityCache<ProductDto, Guid>`).
- Automatic invalidation covers update and delete of the cached entity — you don't clear the cache manually.
- A `[CacheName]` on `Product` or the DTO does **not** change the cache name; the resolved cache-item type is `EntityCacheItemWrapper<TEntityCacheItem>`, so the default name comes from the wrapper.
- Prefer the `*Many*` methods over looping `FindAsync`/`GetAsync`; they batch-fetch only cache-missed ids.
