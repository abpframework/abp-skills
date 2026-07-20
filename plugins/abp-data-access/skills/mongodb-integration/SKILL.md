---
name: mongodb-integration
description: >
  Integrate MongoDB into an ABP application: AbpMongoDbContext, collection mapping, AddMongoDbContext registration, and custom Mongo repositories.
  USE FOR: defining an AbpMongoDbContext, mapping collections with [MongoCollection]/CreateModel, registering via AddMongoDbContext, wiring AddDefaultRepositories/AddRepository, writing custom MongoDbRepository classes, reaching the DbContext via IMongoDbContextProvider, using GetCollectionAsync/GetAggregateAsync.
  DO NOT USE FOR: consuming standard IRepository methods (use-abp-repositories); Entity Framework Core integration, DbContext model builder, or code-first migrations (use ef-core-integration); controlling transaction/UOW boundaries (use manage-units-of-work); soft-delete/multi-tenant/custom query filters or MongoDbRepositoryFilterer (use apply-data-filters); optimistic concurrency (use handle-optimistic-concurrency); connection-string configuration (use configure-connection-strings); seeding data via IDataSeeder (use seed-application-data).
license: MIT
---

# ABP MongoDB Integration

Guidance for the MongoDB data-access layer of an ABP solution. Types live in `Volo.Abp.MongoDB`. The integration lives in the `*.MongoDB` project; repository interfaces belong in the `*.Domain` project.

## When to Use

- Defining an `AbpMongoDbContext` and exposing collections as `IMongoCollection<T>`.
- Naming collections with `[MongoCollection]` and mapping entities in `CreateModel`.
- Registering the DbContext and repositories with `AddMongoDbContext`.
- Writing a custom repository over `MongoDbRepository<TMongoDbContext, TEntity, TKey>`.
- Reaching another collection via `IMongoDbContextProvider<TMongoDbContext>`, or dropping to the native driver with `GetCollectionAsync()` / `GetAggregateAsync()`.

## When Not to Use

- **EF Core data access, `OnModelCreating`, or `dotnet ef` migrations** — use the **ef-core-integration** skill instead.
- **Transaction / Unit of Work boundaries** — use **manage-units-of-work**.
- **Soft-delete / multi-tenant / custom filters** (including `MongoDbRepositoryFilterer`) — use **apply-data-filters**.
- **Optimistic concurrency** — use **handle-optimistic-concurrency**.
- **Connection-string configuration** — use **configure-connection-strings**; **data seeding** — use **seed-application-data**.

## How it works

### DbContext

Derive from `AbpMongoDbContext`. Expose each collection as an `IMongoCollection<T>` property and mark it with `[MongoCollection]` (from `Volo.Abp.MongoDB`) to name the collection. Attach the module's model configuration by overriding `CreateModel`.

```csharp
[ConnectionStringName("Default")]
public class MyProjectMongoDbContext : AbpMongoDbContext
{
    [MongoCollection("AppBooks")]
    public IMongoCollection<Book> Books => Collection<Book>();

    protected override void CreateModel(IMongoModelBuilder modelBuilder)
    {
        base.CreateModel(modelBuilder);

        modelBuilder.Entity<Book>(b =>
        {
            b.CollectionName = "AppBooks";
        });
    }
}
```

- `[MongoCollection]` sets the collection name (`CollectionName` on the attribute); without it the DbContext collection property name is used (e.g. the `Books` property maps to a `Books` collection).
- `Collection<T>()` (defined on `AbpMongoDbContext`) returns the underlying `IMongoCollection<T>`.
- `IMongoModelBuilder.Entity<TEntity>(...)` maps an entity; set `CollectionName`, indexes, or a BSON class map there.
- The base `AbpMongoDbContext.CreateModel` is empty; calling `base.CreateModel(modelBuilder)` is a harmless convention, not a requirement that wires up ABP's entities.

### Module ConfigureXxx() convention

Reusable modules ship a `builder.Configure<Module>()` extension on `IMongoModelBuilder`. Call them inside `CreateModel`:

```csharp
modelBuilder.ConfigurePermissionManagement();
modelBuilder.ConfigureSettingManagement();
```

### Registration

Register in your `*.MongoDB` module's `ConfigureServices` via `AddMongoDbContext<TMongoDbContext>`:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddMongoDbContext<MyProjectMongoDbContext>(options =>
    {
        options.AddDefaultRepositories(includeAllEntities: true);

        // Custom repository override
        options.AddRepository<Book, MongoDbBookRepository>();
    });
}
```

The registration builder shares the same API as EF Core: `AddDefaultRepositories`, `AddDefaultRepository<TEntity>()`, `AddRepository<TEntity, TRepository>()`.

### Custom repositories

Declare the interface in the **Domain** project (same as EF Core — `IRepository<TEntity, TKey>`):

```csharp
public interface IBookRepository : IRepository<Book, Guid>
{
    Task<List<Book>> GetListByAuthorAsync(Guid authorId);
}
```

`IRepository` is the right base inside a **final application**. For a **reusable module** published for other apps, extend `IBasicRepository<Book, Guid>` (or `IReadOnlyBasicRepository`) instead, so consumers aren't coupled to a provider's `IQueryable` (see use-abp-repositories).

Implement in the **MongoDB** project by deriving from `MongoDbRepository<TMongoDbContext, TEntity, TKey>`:

```csharp
public class MongoDbBookRepository
    : MongoDbRepository<MyProjectMongoDbContext, Book, Guid>, IBookRepository
{
    public MongoDbBookRepository(IMongoDbContextProvider<MyProjectMongoDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public async Task<List<Book>> GetListByAuthorAsync(Guid authorId)
    {
        var queryable = await GetQueryableAsync();
        return await queryable.Where(b => b.AuthorId == authorId).ToListAsync();
    }
}
```

#### Querying inside a repository

- `GetQueryableAsync()` → `IQueryable<TEntity>` (LINQ over the collection; the driver translates it).
- `GetCollectionAsync()` → the raw `IMongoCollection<TEntity>` for native driver operations (aggregation, bulk writes).
- `GetAggregateAsync()` → an `IAggregateFluent<TEntity>` for aggregation pipelines.

The base repository already applies ABP's global filters (soft-delete, multi-tenancy) to `GetQueryableAsync()`; going through the raw collection bypasses them.

#### DbContext provider

Inject `IMongoDbContextProvider<TMongoDbContext>` to reach the DbContext directly and get another collection:

```csharp
var dbContext = await _dbContextProvider.GetDbContextAsync();
var authors = dbContext.Collection<Author>();
```

### Differences vs EF Core

- **No migrations.** MongoDB is schemaless — there is no `dotnet ef migrations` step. The startup template's schema migrator (`MongoDb...DbSchemaMigrator`) instead calls `InitializeCollections`, which creates the collections and any configured indexes; the `DbMigrator` console app (if present) also runs `IDataSeeder` to seed data.
- **No relational joins.** You cannot compose cross-collection joins the way you would with EF Core navigation properties. Load related aggregates with separate queries, or model them within the aggregate. Use `GetAggregateAsync()` / `$lookup` only when a real aggregation pipeline is needed.
- **Attribute for naming is `[MongoCollection]`**, not table mapping.
- Everything else — repository interfaces in Domain, `AddDefaultRepositories`, custom repository pattern, `[ConnectionStringName]` — mirrors the EF Core integration, so application/domain code stays provider-agnostic.

## Validation

- The `*.MongoDB` project references `Volo.Abp.MongoDB`; the DbContext derives from `AbpMongoDbContext` and carries `[ConnectionStringName]`.
- Injecting the default `IRepository<Book, Guid>` (or your `IBookRepository`) resolves after `AddMongoDbContext` registration — confirm the app boots and the repository is available.
- Queried results honor ABP's global filters when you go through `GetQueryableAsync()`; a native `GetCollectionAsync()` query returns unfiltered rows.
- The Domain/Application projects do not reference `Volo.Abp.MongoDB` — repository interfaces stay provider-agnostic.

## Common Pitfalls

- **Going through the raw collection (`GetCollectionAsync()`) unexpectedly bypasses ABP's global filters** (soft-delete, multi-tenancy). Use `GetQueryableAsync()` unless you deliberately need native driver operations.
- **Expecting relational joins** — MongoDB has none; load related aggregates with separate queries or model them within the aggregate, and use `$lookup`/`GetAggregateAsync()` only for real aggregation pipelines.
- **Expecting `dotnet ef migrations`** — MongoDB has none. The template's schema migrator calls `InitializeCollections` to create collections and configured indexes, and the `DbMigrator` (if present) additionally seeds data.
- **Omitting `[MongoCollection]`** — the collection is then named after the property, which may not match your intended collection name.
