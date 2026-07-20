---
name: ef-core-integration
description: >
  Integrate Entity Framework Core into an ABP application: AbpDbContext, AddAbpDbContext registration, default/custom repositories, and code-first migrations with DbMigrator.
  USE FOR: defining an AbpDbContext with ConfigureByConvention, registering it via AddAbpDbContext, wiring AddDefaultRepositories/AddRepository, writing custom EfCoreRepository classes, resolving the active DbContext via IDbContextProvider, adding dotnet ef migrations, running the DbMigrator.
  DO NOT USE FOR: consuming the standard IRepository method surface — Get/Find/WithDetails/queryable/bulk (use-abp-repositories); MongoDB integration (use mongodb-integration); controlling transaction/UOW boundaries (use manage-units-of-work); soft-delete/multi-tenant/custom query filters (use apply-data-filters); optimistic concurrency stamps (use handle-optimistic-concurrency); Dapper queries (use query-with-dapper); connection-string resolution/config (use configure-connection-strings); seeding data via IDataSeeder (use seed-application-data).
license: MIT
---

# ABP EF Core Integration

Guidance for the EF Core data-access layer of an ABP solution. Types live in `Volo.Abp.EntityFrameworkCore`. The EF Core integration lives in the `*.EntityFrameworkCore` project; repository interfaces belong in the `*.Domain` project.

## When to Use

- Defining an `AbpDbContext<TDbContext>` and mapping entities with `ConfigureByConvention()`.
- Registering the DbContext and repositories with `AddAbpDbContext` (`AddDefaultRepositories`, `AddRepository`).
- Writing a custom repository over `EfCoreRepository<TDbContext, TEntity, TKey>`.
- Reaching the active DbContext through `IDbContextProvider<TDbContext>` inside a repository.
- Setting up code-first migrations (`dotnet ef migrations`) and running the `DbMigrator` console app.

## When Not to Use

- **MongoDB data access** — use the **mongodb-integration** skill instead.
- **Transaction / Unit of Work boundaries** (`[UnitOfWork]`, `IUnitOfWorkManager.Begin`, `SaveChangesAsync`) — use **manage-units-of-work**.
- **Soft-delete / multi-tenant / custom global query filters** — use **apply-data-filters**.
- **Optimistic concurrency** (`IHasConcurrencyStamp`) — use **handle-optimistic-concurrency**.
- **Raw SQL via Dapper** — use **query-with-dapper**.
- **Connection-string configuration** — use **configure-connection-strings**; **data seeding** — use **seed-application-data**.

## How it works

### DbContext

Derive from `AbpDbContext<TDbContext>` (which itself derives from EF Core's `DbContext`). Mark it with `[ConnectionStringName]` (from `Volo.Abp.Data`) so ABP resolves the right connection string.

```csharp
[ConnectionStringName("Default")]
public class MyProjectDbContext : AbpDbContext<MyProjectDbContext>
{
    public DbSet<Book> Books { get; set; }

    public MyProjectDbContext(DbContextOptions<MyProjectDbContext> options)
        : base(options)
    {
    }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder); // required — applies ABP conventions (audit/soft-delete/extra-props/concurrency) to entities already in the model

        builder.Entity<Book>(b =>
        {
            b.ToTable("AppBooks");
            b.ConfigureByConvention(); // applies ABP conventions (audit props, extra props, soft-delete, concurrency stamp)
            b.Property(x => x.Name).IsRequired().HasMaxLength(128);
        });
    }
}
```

`ConfigureByConvention()` is an extension on `EntityTypeBuilder` from `Volo.Abp.EntityFrameworkCore.Modeling`. Always call `base.OnModelCreating(builder)` first.

### Module ConfigureXxx() convention

Reusable modules expose a `builder.ConfigureXxx()` extension so a host DbContext can map the module's tables. Call them inside `OnModelCreating`:

```csharp
builder.ConfigurePermissionManagement();
builder.ConfigureSettingManagement();
builder.ConfigureAuditLogging();
```

When you author a module, follow the same pattern: ship a `<Module>DbContextModelCreatingExtensions` class with a `Configure<Module>(this ModelBuilder builder)` extension.

### Registration

Register the DbContext and repositories in your `*.EntityFrameworkCore` module's `ConfigureServices` via `AddAbpDbContext<TDbContext>`:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddAbpDbContext<MyProjectDbContext>(options =>
    {
        // Register a default IRepository<TEntity, TKey> for every aggregate root
        options.AddDefaultRepositories(includeAllEntities: true);

        // Or override a single entity with a custom repository implementation
        options.AddRepository<Book, EfCoreBookRepository>();
    });
}
```

- `AddDefaultRepositories(includeAllEntities: true)` also registers repositories for entities that are not aggregate roots.
- `AddDefaultRepository<TEntity>()` registers just one.
- `AddRepository<TEntity, TRepository>()` binds a custom repository.

### Custom repositories

Declare the interface in the **Domain** project:

```csharp
public interface IBookRepository : IRepository<Book, Guid>
{
    Task<List<Book>> GetListByAuthorAsync(Guid authorId);
}
```

`IRepository` is the right base inside a **final application**. For a **reusable module** published for other apps, extend `IBasicRepository<Book, Guid>` (or `IReadOnlyBasicRepository`) instead, so consumers aren't coupled to a provider's `IQueryable` (see use-abp-repositories).

Implement in the **EntityFrameworkCore** project by deriving from `EfCoreRepository<TDbContext, TEntity, TKey>`:

```csharp
public class EfCoreBookRepository
    : EfCoreRepository<MyProjectDbContext, Book, Guid>, IBookRepository
{
    public EfCoreBookRepository(IDbContextProvider<MyProjectDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public async Task<List<Book>> GetListByAuthorAsync(Guid authorId)
    {
        var dbSet = await GetDbSetAsync();
        return await dbSet.Where(b => b.AuthorId == authorId).ToListAsync();
    }
}
```

#### Querying inside a repository

- `GetQueryableAsync()` → `IQueryable<TEntity>` for LINQ composition.
- `GetDbSetAsync()` → the raw `DbSet<TEntity>`.
- `GetDbContextAsync()` → the `TDbContext` when you need `Set<TOther>()`, `Database`, etc.

```csharp
var queryable = await GetQueryableAsync();
var query = queryable.Where(b => b.Name.Contains(filter));
```

Prefer these async accessors over old sync members (`DbSet`, `DbContext`) — the sync ones are `[Obsolete]`.

### IDbContextProvider

`IDbContextProvider<TDbContext>` resolves the active DbContext for the current unit of work (handling transactions/connection-string routing). It lives in `Volo.Abp.EntityFrameworkCore`, so only the **EntityFrameworkCore** project should touch it — keep DbContext access inside a custom repository, not a domain/application service. Injecting it into the Domain or Application layer forces those layers to reference EF Core, which breaks the layering and the encapsulation the repository pattern exists to provide.

Declare the repository interface in the **Domain** project (no EF Core types leak out):

```csharp
public interface IBookRepository : IRepository<Book, Guid>
{
    Task DoAsync();
}
```

Implement it in the **EntityFrameworkCore** project, where `IDbContextProvider<TDbContext>` is available (`EfCoreRepository` already gets one via its base constructor, so call `GetDbContextAsync()` directly):

```csharp
public class EfCoreBookRepository
    : EfCoreRepository<MyProjectDbContext, Book, Guid>, IBookRepository
{
    public EfCoreBookRepository(IDbContextProvider<MyProjectDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public async Task DoAsync()
    {
        var dbContext = await GetDbContextAsync();
        // use dbContext.Books ...
    }
}
```

Domain/application services then depend on `IBookRepository`, staying free of any EF Core reference.

### Code-first migrations

In a layered ABP solution, migrations live in a dedicated project (typically `*.EntityFrameworkCore` or a separate `*.DbMigrations`) and a `*.DbMigrator` console app applies them + seeds data.

Add a migration and update the database from the project holding the DbContext:

```bash
dotnet ef migrations add Added_Books
dotnet ef database update
```

Run the migrator console app to apply pending migrations and run data seeders (recommended for CI/deploy):

```bash
dotnet run --project src/MyProject.DbMigrator
```

The `DbMigrator` uses `IDataSeeder` to seed initial data (admin user, permissions, etc.) after migrating.

## Switching the DBMS provider

The startup template ships SQL Server (`Volo.Abp.EntityFrameworkCore.SqlServer` + `AbpEntityFrameworkCoreSqlServerModule` + `UseSqlServer()`). To switch, do three edits in the `*.EntityFrameworkCore` project, then regenerate migrations.

**1. Swap the NuGet package** (use the same version as the SqlServer one you remove):

| DBMS | NuGet package | ABP module (`[DependsOn]`) | `UseXxx()` call |
| --- | --- | --- | --- |
| MySQL | `Volo.Abp.EntityFrameworkCore.MySQL` | `AbpEntityFrameworkCoreMySQLModule` | `UseMySQL()` |
| MySQL (Pomelo) | `Volo.Abp.EntityFrameworkCore.MySQL.Pomelo` | `AbpEntityFrameworkCoreMySQLPomeloModule` | `UseMySQL()` |
| PostgreSQL | `Volo.Abp.EntityFrameworkCore.PostgreSql` | `AbpEntityFrameworkCorePostgreSqlModule` | `UseNpgsql()` |
| Oracle (official) | `Volo.Abp.EntityFrameworkCore.Oracle` | `AbpEntityFrameworkCoreOracleModule` | `UseOracle()` |
| Oracle (Devart) | `Volo.Abp.EntityFrameworkCore.Oracle.Devart` | `AbpEntityFrameworkCoreOracleDevartModule` | `UseOracle()` |
| SQLite | `Volo.Abp.EntityFrameworkCore.Sqlite` | `AbpEntityFrameworkCoreSqliteModule` | `UseSqlite()` |

**2. Replace the module dependency** in your `*EntityFrameworkCoreModule`: drop `typeof(AbpEntityFrameworkCoreSqlServerModule)` from `[DependsOn]`, add the new one, and swap the matching `using` (e.g. `using Volo.Abp.EntityFrameworkCore.PostgreSql;`).

**3. Replace the `UseXxx()` call.** The `UseSqlServer()` / `UseMySQL()` / `UseNpgsql()` / `UseOracle()` / `UseSqlite()` extensions on `AbpDbContextOptions` live in `Volo.Abp.EntityFrameworkCore` (they delegate to the `AbpDbContextConfigurationContext` extension of the same name, which routes `ExistingConnection` vs `ConnectionString` and sets `SplitQuery`):

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    Configure<AbpDbContextOptions>(options =>
    {
        options.UseNpgsql(); // was options.UseSqlServer();
    });
}
```

Change the same call in `*DbContextFactory.cs` (the design-time factory used by `dotnet ef`) — there it's on `DbContextOptionsBuilder`, e.g. `.UseNpgsql(configuration.GetConnectionString("Default"))`.

Provider-specific notes from the docs:

- **PostgreSQL**: `UsePostgreSql()` is `[Obsolete]` — use `UseNpgsql()`. Enable `AppContext.SetSwitch("Npgsql.EnableLegacyTimestampBehavior", true)` in `PreConfigureServices` and in the design-time factory.
- **Oracle**: ABP ships two separate integrations — `Volo.Abp.EntityFrameworkCore.Oracle` (ODP.NET driver) and `Volo.Abp.EntityFrameworkCore.Oracle.Devart` (Devart driver). Pick one; both expose `UseOracle()`. Requires Oracle v12.2+ (128-byte identifier limit), and long `string` columns may need `long`/`clob` conversion migrations.
- **MySQL**: both modules expose an ABP `UseMySQL()` extension — `Volo.Abp.EntityFrameworkCore.MySQL` runs on the MySql.EntityFrameworkCore driver, while `Volo.Abp.EntityFrameworkCore.MySQL.Pomelo` runs on the Pomelo driver and auto-detects the `ServerVersion` (via `ServerVersion.AutoDetect`), so you don't pass one.

**Regenerate migrations.** EF Core migrations contain provider-specific SQL, so the existing ones won't apply on a new provider. Also swap the `appsettings.json` connection strings (in `.DbMigrator`, `.Web`, etc.) to the new provider's format.

- **New / undeployed project** (no database has been migrated from these files yet): delete the `Migrations` folder under the `*.EntityFrameworkCore` project, rebuild, add a fresh `Initial` migration (`dotnet ef migrations add Initial`), then run the `*.DbMigrator` to create the database and seed.
- **Existing project with a deployed migration history**: do **not** delete the folder — that discards the history and breaks the upgrade chain for any deployed database. Back up first, plan the provider switch as a data migration, and get explicit sign-off before changing the migration history.

## Validation

- The `*.EntityFrameworkCore` project references `Volo.Abp.EntityFrameworkCore`; the DbContext derives from `AbpDbContext<TDbContext>` and carries `[ConnectionStringName]`.
- `OnModelCreating` calls `base.OnModelCreating(builder)` and `ConfigureByConvention()` on each mapped entity.
- Injecting the default `IRepository<Book, Guid>` (or your `IBookRepository`) resolves after `AddAbpDbContext` registration — confirm the app boots and the repository is available.
- `dotnet ef migrations add ...` generates a migration; `dotnet run --project src/MyProject.DbMigrator` applies pending migrations and runs seeders without error.
- The Domain/Application projects do not reference `Volo.Abp.EntityFrameworkCore` — repository interfaces stay EF-free.

## Common Pitfalls

- **Forgetting `base.OnModelCreating(builder)`** — without it `AbpDbContext` can't apply its property/value-converter conventions (audit, soft-delete, extra properties, concurrency stamp) to the entities in the model. Call it first. It configures entities *already in the model*; ABP module entities (Identity, Permission Management, etc.) are still mapped separately by each module's own `builder.ConfigureXxx()` extension.
- **Using the sync `DbSet`/`DbContext` members** — they are `[Obsolete]`; use the async `GetDbSetAsync()` / `GetDbContextAsync()` / `GetQueryableAsync()` accessors.
- **Injecting `IDbContextProvider<TDbContext>` into a Domain or Application service** — it forces those layers to reference EF Core and breaks layering. Keep DbContext access inside a custom repository in the EntityFrameworkCore project.
- **`AddDefaultRepositories()` without `includeAllEntities: true`** — non-aggregate-root entities won't get a default repository.
