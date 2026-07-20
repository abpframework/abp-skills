---
name: seed-application-data
description: >
  Seed initial or default data into an ABP app or module using ABP's provider-independent data seed system (IDataSeedContributor + IDataSeeder).
  USE FOR: adding admin user/roles/lookup tables/demo records, seeding per tenant via DataSeedContext.TenantId, running seeding from the .DbMigrator project, seeding data for automated tests.
  DO NOT USE FOR: schema migrations or EF Core HasData seeding (use ef-core-integration), MongoDB collection setup (use mongodb-integration), tenant creation/routing itself (use configure-multi-tenancy), unit-of-work sizing beyond SeedInSeparateUowAsync (use manage-units-of-work).
license: MIT
---

# Seed Application Data in ABP

ABP has its own data seed system (not EF Core's). It is modular, database-provider independent (works with EF Core and MongoDB), production-ready, and DI-enabled. Prefer it over EF Core's `HasData` seeding.

## When to Use

- You need to add initial/default data (admin user, roles, lookup tables, demo records) to an ABP app or module.
- You want provider-independent seeding that runs the same way on EF Core and MongoDB.
- You need to seed per tenant, honoring `DataSeedContext.TenantId`.
- You need to seed data for automated tests.

## When Not to Use

- **Schema migrations or EF Core `HasData` seeding** — use ef-core-integration.
- **MongoDB collection/index setup** — use mongodb-integration.
- **Creating tenants or routing them to databases** — use configure-multi-tenancy (this skill only writes data into an existing tenant scope).
- **Fine-grained unit-of-work sizing** beyond `SeedInSeparateUowAsync` — use manage-units-of-work.

## Workflow

### 1. Write a data seed contributor

Implement `IDataSeedContributor` (from `Volo.Abp.Data`). Register it for DI (e.g. `ITransientDependency`) and ABP discovers and runs it automatically as part of the seed process. The interface has a single method:

```csharp
public interface IDataSeedContributor
{
    Task SeedAsync(DataSeedContext context);
}
```

Example — seed one book only if the table is empty:

```csharp
using System;
using System.Threading.Tasks;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Guids;
using Volo.Abp.MultiTenancy;

public class BookStoreDataSeedContributor
    : IDataSeedContributor, ITransientDependency
{
    private readonly IRepository<Book, Guid> _bookRepository;
    private readonly IGuidGenerator _guidGenerator;
    private readonly ICurrentTenant _currentTenant;

    public BookStoreDataSeedContributor(
        IRepository<Book, Guid> bookRepository,
        IGuidGenerator guidGenerator,
        ICurrentTenant currentTenant)
    {
        _bookRepository = bookRepository;
        _guidGenerator = guidGenerator;
        _currentTenant = currentTenant;
    }

    public async Task SeedAsync(DataSeedContext context)
    {
        using (_currentTenant.Change(context?.TenantId))
        {
            if (await _bookRepository.GetCountAsync() > 0)
            {
                return;
            }

            var book = new Book(
                id: _guidGenerator.Create(),
                name: "The Hitchhiker's Guide to the Galaxy",
                price: 42);

            await _bookRepository.InsertAsync(book);
        }
    }
}
```

Guidelines:

- Make the seed **idempotent** — check the DB first (e.g. `GetCountAsync()`) and return early if data already exists, so re-running the seeder is safe.
- You can inject any service; a contributor can do much more than plain inserts.

### 2. Use DataSeedContext and TenantId

`DataSeedContext` (from `Volo.Abp.Data`) carries the target tenant and free-form properties:

```csharp
public class DataSeedContext
{
    public Guid? TenantId { get; set; }
    public Dictionary<string, object?> Properties { get; }
    public object? this[string name] { get; set; }         // shortcut for Properties[name]
    public DataSeedContext(Guid? tenantId = null) { ... }
    public virtual DataSeedContext WithProperty(string key, object? value); // fluent
}
```

To seed **per tenant**, honor `context.TenantId`. Wrap your logic in `ICurrentTenant.Change(context?.TenantId)` (as above) so entities are written in the correct tenant scope. `TenantId == null` means the host.

### 3. Run seeding from IDataSeeder

`IDataSeeder` is the entry point that runs all contributors:

```csharp
public interface IDataSeeder
{
    Task SeedAsync(DataSeedContext context);
}
```

You rarely call it directly in app code — the layered startup template's `.DbMigrator` console project already invokes it. When you do call it, pass configuration via properties, which contributors read from `context`:

```csharp
// Read the admin credentials from configuration / a secret store — don't hardcode or commit them
await _dataSeeder.SeedAsync(
    new DataSeedContext()
        .WithProperty("AdminEmail", configuration["App:AdminEmail"])
        .WithProperty("AdminPassword", configuration["App:AdminPassword"]));
```

Convenience overloads live in `DataSeederExtensions`:

```csharp
// Seed for a specific tenant (wraps a new DataSeedContext(tenantId)):
await _dataSeeder.SeedAsync(tenantId);

// One separate unit of work per contributor — avoids DB timeouts when there
// are many contributors or a lot of data written in a single transaction.
// options must not be null (Begin runs Check.NotNull on it); pass
// requiresNew: true so each contributor gets its own independent UOW instead
// of a child of the seeder's ambient [UnitOfWork]:
await _dataSeeder.SeedInSeparateUowAsync(
    tenantId: null,
    options: new AbpUnitOfWorkOptions(),
    requiresNew: true);
```

### 4. Know where seeding runs

- **Production & development**: the `*.DbMigrator` console app (in the layered startup template) migrates the schema and seeds data. Run it on each deploy. It also handles multi-tenant setups where each tenant has its own database, migrating and seeding every database. Running seeding in a dedicated app (rather than at web-app startup) makes app start faster and works safely in clustered/multi-instance deployments.
- **Testing**: call `IDataSeeder.SeedAsync()` from the test base module's `OnApplicationInitialization`. To add data unique to tests, drop an extra `IDataSeedContributor` into the test project — it is discovered and run alongside the production contributors.

## Validation

- Run the `*.DbMigrator` console app (or `IDataSeeder.SeedAsync()`) and confirm the expected rows/documents appear in the database.
- Run the seeder a second time and confirm no duplicate rows are created — proving the idempotency guard (`GetCountAsync()` early return) works.
- For per-tenant seeding, confirm the data lands under the intended `TenantId` scope (and under the host when `TenantId == null`).

## Common Pitfalls

- **A non-idempotent contributor inserts duplicates on re-run.** Always check the DB first and return early if data already exists.
- **`SeedInSeparateUowAsync` options must not be null** — `Begin` runs `Check.NotNull` on it; pass `new AbpUnitOfWorkOptions()` and `requiresNew: true` so each contributor gets its own independent UOW instead of a child of the seeder's ambient `[UnitOfWork]`.
- **Contributors run inside a single unit of work by default.** If that UoW grows too large (many contributors / lots of data), use `SeedInSeparateUowAsync` to avoid DB timeouts.
- **Pre-built modules ship their own contributors** — e.g. the Identity module seeds the admin role/user and reads `AdminEmail` / `AdminPassword` from the context; don't re-implement what a module already seeds.
- **Ignoring `context.TenantId`** writes data into the wrong tenant scope; always wrap logic in `ICurrentTenant.Change(context?.TenantId)`.
