---
name: apply-data-filters
description: >
  Work with ABP data filters — the built-in ISoftDelete and IMultiTenant filters, toggling them via IDataFilter scopes, changing default states, and defining custom global query filters for EF Core or MongoDB.
  USE FOR: reading/writing soft-deleted or cross-tenant data with IDataFilter.Disable/Enable, checking IsEnabled, HardDeleteAsync, changing AbpDataFilterOptions defaults, defining a custom marker-interface filter, wiring it in EF Core (ShouldFilterEntity/CreateFilterExpression/HasAbpQueryFilter) or MongoDB (MongoDbRepositoryFilterer/FilterQueryable).
  DO NOT USE FOR: switching the active tenant context via ICurrentTenant.Change (that is the multi-tenancy concern); defining a DbContext/repositories or EF Core migrations (use ef-core-integration); MongoDB DbContext/repository setup (use mongodb-integration); transaction/UOW boundaries (use manage-units-of-work); optimistic concurrency (use handle-optimistic-concurrency).
license: MIT
---

# Apply ABP Data Filters

`Volo.Abp.Data` provides **data filters** that automatically filter rows when querying the database. Filters are keyed by a marker interface implemented on the entity (`ISoftDelete`, `IMultiTenant`, or your own).

## When to Use

- Reading soft-deleted or cross-tenant rows by disabling `ISoftDelete` / `IMultiTenant` in an `IDataFilter` scope.
- Checking a filter's current state with `IsEnabled<TFilter>()`, or physically removing a soft-delete row with `HardDeleteAsync`.
- Changing whether a filter is enabled by default via `AbpDataFilterOptions`.
- Defining a custom marker-interface filter and wiring it for EF Core or MongoDB.

## When Not to Use

- **Switching the active tenant context** (`ICurrentTenant.Change`) — that is the multi-tenancy concern, **not** a data-filter one.
- **Defining a DbContext, repositories, or EF Core migrations** — use the **ef-core-integration** skill.
- **MongoDB DbContext / repository setup** — use **mongodb-integration**.
- **Transaction / Unit of Work boundaries** — use **manage-units-of-work**.
- **Optimistic concurrency** — use **handle-optimistic-concurrency**.

## How it works

### Built-in filters

#### `ISoftDelete`

Marks an entity as deleted instead of physically removing it. Implement `ISoftDelete` to add a `bool IsDeleted` property:

```csharp
public class Book : AggregateRoot<Guid>, ISoftDelete
{
    public string Name { get; set; }
    public bool IsDeleted { get; set; } // defined by ISoftDelete
}
```

When you delete via a repository, ABP sets `IsDeleted = true` and blocks the real delete, and it **automatically excludes** soft-deleted rows from queries. The filter is **enabled by default** — you cannot read deleted rows unless you explicitly disable it. Use `HardDeleteAsync` on the repository to physically remove a soft-delete entity.

#### `IMultiTenant`

Isolates data per tenant. Implement `IMultiTenant` to add a nullable `TenantId`:

```csharp
public class Book : AggregateRoot<Guid>, ISoftDelete, IMultiTenant
{
    public string Name { get; set; }
    public bool IsDeleted { get; set; }   // ISoftDelete
    public Guid? TenantId { get; set; }    // IMultiTenant
}
```

ABP automatically filters queries to the **current tenant** based on `TenantId`. (To switch tenant context you use `ICurrentTenant.Change`, which is the multi-tenancy concern, not the data-filter one.)

### Enabling / disabling filters: `IDataFilter`

Inject `IDataFilter` and toggle a filter inside a `using` block. The `IDisposable` restores the previous state when the block ends:

```csharp
public class MyBookService : ITransientDependency
{
    private readonly IDataFilter _dataFilter;
    private readonly IRepository<Book, Guid> _bookRepository;

    public MyBookService(IDataFilter dataFilter, IRepository<Book, Guid> bookRepository)
    {
        _dataFilter = dataFilter;
        _bookRepository = bookRepository;
    }

    public async Task<List<Book>> GetAllIncludingDeletedAsync()
    {
        using (_dataFilter.Disable<ISoftDelete>())
        {
            return await _bookRepository.GetListAsync(); // includes soft-deleted rows
        }
    }
}
```

`IDataFilter` members:

- `IDisposable Disable<TFilter>()` — disable a filter for the scope.
- `IDisposable Enable<TFilter>()` — enable a filter for the scope.
- `bool IsEnabled<TFilter>()` — check current state.

`Enable` and `Disable` **nest**, so you can define inner scopes and each restores the outer state on dispose. **Always** call them inside a `using` block so the state resets even on exception.

#### Generic `IDataFilter<TFilter>`

For a single filter you can inject the strongly-typed version and drop the type argument:

```csharp
private readonly IDataFilter<ISoftDelete> _softDeleteFilter;
// ...
using (_softDeleteFilter.Disable())
{
    return await _bookRepository.GetListAsync();
}
```

It exposes `Enable()`, `Disable()`, and `IsEnabled` — all bound to `TFilter`.

### Changing default filter state

Use `AbpDataFilterOptions` to change whether a filter is enabled by default. Example — disable soft delete globally (queries then include deleted rows unless you enable it):

```csharp
Configure<AbpDataFilterOptions>(options =>
{
    options.DefaultStates[typeof(ISoftDelete)] = new DataFilterState(isEnabled: false);
});
```

Be careful changing defaults for built-in filters, especially when using pre-built modules that assume soft delete is on. Changing defaults for **your own** filters is safe.

### Defining a custom filter

Start with a marker interface and implement it on entities:

```csharp
public interface IIsActive
{
    bool IsActive { get; }
}

public class Book : AggregateRoot<Guid>, IIsActive
{
    public string Name { get; set; }
    public bool IsActive { get; set; }
}
```

How the filter is actually **applied to queries depends on the database provider** — you implement it once per provider you use.

#### EF Core

ABP maps filters onto EF Core's **global query filters**, so they work even when you use `DbContext` directly. Override `ShouldFilterEntity` and `CreateFilterExpression` in your `DbContext`:

```csharp
protected bool IsActiveFilterEnabled => DataFilter?.IsEnabled<IIsActive>() ?? false;

protected override bool ShouldFilterEntity<TEntity>(IMutableEntityType entityType)
{
    if (typeof(IIsActive).IsAssignableFrom(typeof(TEntity)))
    {
        return true;
    }
    return base.ShouldFilterEntity<TEntity>(entityType);
}

protected override Expression<Func<TEntity, bool>>? CreateFilterExpression<TEntity>(
    ModelBuilder modelBuilder,
    EntityTypeBuilder<TEntity> entityTypeBuilder)
{
    var expression = base.CreateFilterExpression<TEntity>(modelBuilder, entityTypeBuilder);
    if (typeof(IIsActive).IsAssignableFrom(typeof(TEntity)))
    {
        Expression<Func<TEntity, bool>> isActiveFilter =
            e => !IsActiveFilterEnabled || EF.Property<bool>(e, "IsActive");
        expression = expression == null
            ? isActiveFilter
            : QueryFilterExpressionHelper.CombineExpressions(expression, isActiveFilter);
    }
    return expression;
}
```

Note the guard `!IsActiveFilterEnabled || ...` — the filter is applied only while it's enabled, which is what makes `Disable<IIsActive>()` work. For a single entity you can also chain onto ABP's built-in filters with `b.HasAbpQueryFilter(e => e.Name.StartsWith("abp"))` inside `OnModelCreating`.

#### MongoDB

For MongoDB, filtering goes through `IMongoDbRepositoryFilterer` and only works when you use the repositories. To add a filter for one entity, derive `MongoDbRepositoryFilterer<Book, Guid>`, override `FilterQueryable`, and expose it:

```csharp
[ExposeServices(typeof(IMongoDbRepositoryFilterer<Book, Guid>))]
public class BookMongoDbRepositoryFilterer
    : MongoDbRepositoryFilterer<Book, Guid>, ITransientDependency
{
    public BookMongoDbRepositoryFilterer(IDataFilter dataFilter, ICurrentTenant currentTenant)
        : base(dataFilter, currentTenant) { }

    public override TQueryable FilterQueryable<TQueryable>(TQueryable query)
    {
        if (DataFilter.IsEnabled<IIsActive>())
        {
            return (TQueryable)query.Where(x => x.IsActive);
        }
        return base.FilterQueryable(query);
    }
}
```

The query filter is `FilterQueryable` — the repository's `IQueryable`/`GetListAsync` pipeline runs each registered `IMongoDbRepositoryFilterer<TEntity>` (and, for keyed repositories, `IMongoDbRepositoryFilterer<TEntity, TKey>`) through it. So register your subclass for the matching filterer interface; if the entity is used through a keyed repository (`IRepository<Book, Guid>`), expose `IMongoDbRepositoryFilterer<Book, Guid>` and derive `MongoDbRepositoryFilterer<Book, Guid>` (as above) so the keyed pipeline picks it up.

`AddGlobalFiltersAsync` is a **different** hook: it builds native MongoDB `FilterDefinition<TEntity>`s used by the entity/id operations (`CreateEntityFilterAsync` / `CreateEntitiesFilterAsync` for get-by-id, delete, concurrency), **not** the queryable pipeline. Don't override it to add a global query filter — override `FilterQueryable` for that. The key point is the same as EF Core: honor `DataFilter.IsEnabled<...>()` so `Disable`/`Enable` scopes take effect.

## Validation

- By default a repository query excludes soft-deleted (`IsDeleted = true`) rows and rows outside the current tenant; the same query inside `_dataFilter.Disable<ISoftDelete>()` returns the deleted rows too.
- `IDataFilter.IsEnabled<TFilter>()` reflects the current scope's state and reverts when the `using` block ends (even on exception).
- For a custom EF Core filter, confirm the generated SQL includes the guard so `Disable<IIsActive>()` returns the otherwise-filtered rows.
- For a custom MongoDB filter, confirm the filtered rows appear only when going through the repository (the filterer runs there), and honor `DataFilter.IsEnabled<...>()`.

## Common Pitfalls

- **Toggling a filter without a `using` block** — the state won't reset on exception (or at all). Always scope `Enable`/`Disable` in `using`.
- **Changing `AbpDataFilterOptions` defaults for built-in filters** — pre-built modules assume soft delete is on; changing that globally can break them. Changing defaults for your **own** filters is safe.
- **Custom filter with no enabled-guard** — omit `!IsActiveFilterEnabled || ...` (EF Core) or the `IsEnabled<...>()` check (MongoDB) and `Disable`/`Enable` scopes silently do nothing.
- **MongoDB filters bypassed via the raw collection** — the filterer only runs through the repositories; native driver access is unfiltered.
- **Confusing tenant filtering with tenant switching** — `IMultiTenant` filters to the current tenant; changing the active tenant is `ICurrentTenant.Change`, a separate multi-tenancy concern.
