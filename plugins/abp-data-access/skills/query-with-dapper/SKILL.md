---
name: query-with-dapper
description: >
  Run raw SQL via Dapper inside an ABP repository for hot-path read/aggregate queries while sharing ABP's unit of work, connection, and transaction.
  USE FOR: complex or slow queries where EF Core's generated SQL is too slow, hand-written SQL you want full control over, deriving from a DbContext-based DapperRepository and using GetDbConnectionAsync/GetDbTransactionAsync to stay in the current unit of work.
  DO NOT USE FOR: standard CRUD/LINQ/change tracking/migrations (use ef-core-integration), MongoDB queries (use mongodb-integration), unit-of-work configuration itself (use manage-units-of-work), connection string routing (use configure-connection-strings).
license: MIT
---

# Query with Dapper in ABP

ABP's `Volo.Abp.Dapper` integration lets you write raw-SQL repositories with [Dapper](https://github.com/DapperLib/Dapper) while staying inside ABP's unit of work. The integration is **built on top of EF Core**: EF Core stays the primary provider and you reach for Dapper only to fine-tune specific queries for maximum performance.

## When to Use

- A heavy read or aggregate query where EF Core's generated SQL is too slow.
- SQL you want full hand control over, on a hot path.
- You want raw SQL that still participates in ABP's unit of work, connection, and transaction.

## When Not to Use

- **Standard CRUD, LINQ, change tracking, entities, migrations** — use ef-core-integration; use it for almost everything.
- **MongoDB queries** — use mongodb-integration; the Dapper integration requires an EF Core `DbContext`.
- **Configuring the unit of work itself** — use manage-units-of-work (this skill only borrows the ambient UoW).
- **Connection string / per-tenant database routing setup** — use configure-connection-strings (Dapper inherits routing from the underlying `DbContext`).

## Workflow

### 1. Choose Dapper vs EF Core

- **EF Core (default)** — CRUD, change tracking, LINQ, entities, migrations. Use it for almost everything.
- **Dapper** — a heavy read or aggregate query where EF Core's generated SQL is too slow, or SQL you want full hand control over. Dapper is a lightweight, high-performance object mapper for these hot paths.

You mix the two in the same app. The Dapper integration requires an EF Core `DbContext` — it borrows that context's connection and transaction, so both share the same unit of work.

### 2. Install the package

Run in the folder of the `.csproj` you want the package in (the database/EF Core layer in a layered solution):

```bash
abp add-package Volo.Abp.Dapper
```

### 3. Implement a Dapper repository

Derive from `DapperRepository<TDbContext>` (namespace `Volo.Abp.Domain.Repositories.Dapper`), where `TDbContext` is your EF Core `DbContext`. Register it for DI. It implements `IUnitOfWorkEnabled`, so ABP makes the current connection/transaction available in method bodies via dynamic proxying (interception).

```csharp
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Dapper;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Repositories.Dapper;
using Volo.Abp.EntityFrameworkCore;

public class PersonDapperRepository :
    DapperRepository<MyAppDbContext>, ITransientDependency
{
    public PersonDapperRepository(IDbContextProvider<MyAppDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public virtual async Task<List<string>> GetAllPersonNamesAsync()
    {
        var dbConnection = await GetDbConnectionAsync();
        return (await dbConnection.QueryAsync<string>(
            "select Name from People",
            transaction: await GetDbTransactionAsync())
        ).ToList();
    }

    public virtual async Task<int> UpdatePersonNameAsync(Guid id, string name)
    {
        var dbConnection = await GetDbConnectionAsync();
        // Always scope a write with a WHERE clause — without it this updates every row.
        return await dbConnection.ExecuteAsync(
            "update People set Name = @NewName where Id = @Id",
            new { Id = id, NewName = name },
            await GetDbTransactionAsync());
    }
}
```

### 4. Preserve the unit of work + connection resolution

The base class hands you the ambient connection and transaction that ABP's unit of work is managing — do not open your own connection:

```csharp
public virtual async Task<IDbConnection> GetDbConnectionAsync();      // current UoW connection
public virtual async Task<IDbTransaction?> GetDbTransactionAsync();   // current UoW transaction (null if none)
```

Because these come from the shared `IDbContextProvider<TDbContext>`:

- **Always pass `await GetDbTransactionAsync()`** to your Dapper calls, so raw SQL participates in the same transaction as EF Core writes — otherwise your Dapper query may not see uncommitted changes and won't roll back with the UoW.
- Connection resolution (including multi-tenant per-tenant database routing and `[ConnectionStringName]`) is inherited from the underlying `DbContext`, so Dapper hits the same database EF Core would for that context.
- The bare `DbConnection` / `DbTransaction` properties exist but are `[Obsolete]` — use the async methods.

Rules:

- **Make query methods `virtual`.** Interception (which supplies the connection/transaction) only works on virtual members.
- The repository resolves its `DbContext` through `IDbContextProvider<TDbContext>`, which must be a configured ABP EF Core `DbContext` (the startup template configures this for you).

### 5. Layered solution tip

Define an `IPersonDapperRepository` interface in the domain layer and implement it in the database/EF Core layer. Inject the interface where you need it, keeping the raw SQL out of the domain and application layers.

## Validation

- After `abp add-package Volo.Abp.Dapper`, confirm the package reference appears in the target `.csproj`.
- Call a Dapper method inside a unit of work that also does EF Core writes; the query should see those uncommitted writes (proving it shares the connection/transaction) and roll back with the UoW. Dapper won't see EF Core's pending changes while they're still in the `ChangeTracker` — flush them first with `autoSave: true` on the write or by calling `SaveChangesAsync()` before the Dapper query.
- Confirm query methods are `virtual` — if interception is missing, `GetDbConnectionAsync()`/`GetDbTransactionAsync()` won't resolve the ambient UoW.

## Common Pitfalls

- **Opening your own connection** breaks the shared unit of work. Always use `GetDbConnectionAsync()` / `GetDbTransactionAsync()` from the base class.
- **Not passing `await GetDbTransactionAsync()`** to Dapper calls means the raw SQL may not see uncommitted EF Core changes and won't roll back with the UoW.
- **Non-`virtual` query methods** skip interception, so the ambient connection/transaction is never supplied.
- **Using the bare `DbConnection` / `DbTransaction` properties** — they are `[Obsolete]`; use the async methods.

## See also

- ABP Dapper integration docs (`framework/data/dapper`)
- ABP EF Core integration docs
