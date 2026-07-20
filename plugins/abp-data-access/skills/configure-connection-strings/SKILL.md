---
name: configure-connection-strings
description: >
  Configure ABP connection strings for modular and multi-tenant apps — the Default connection, per-module databases, grouping modules into one database, and per-tenant database routing.
  USE FOR: setting the Default connection, giving a module its own database with a named entry, binding a DbContext via [ConnectionStringName], mapping several modules to one DB with AbpDbConnectionOptions.Databases, routing a tenant to its own database, customizing IConnectionStringResolver.
  DO NOT USE FOR: EF Core DbContext registration/model config (use ef-core-integration), MongoDB client/database setup (use mongodb-integration), creating tenants or the tenant store (use configure-multi-tenancy), unit-of-work/transaction handling (use manage-units-of-work).
license: MIT
---

# Configure Connection Strings in ABP

ABP's connection string system is designed for modular and multi-tenant apps: every module can point at its own physical database, and every tenant can use a separate database. A single monolithic app with one DB just uses `Default`.

## When to Use

- You need to set the `Default` connection for a single-database app.
- You want to give a module its own physical database with a named connection string.
- You want to bind a `DbContext` to a named connection string via `[ConnectionStringName]`.
- You want to group several modules into one shared database with `AbpDbConnectionOptions.Databases`.
- You need per-tenant database routing in a multi-tenant SaaS app.
- You need custom connection-string resolution logic via `IConnectionStringResolver`.

## When Not to Use

- **EF Core `DbContext` registration or model configuration** — use ef-core-integration.
- **MongoDB client/database setup** — use mongodb-integration.
- **Creating tenants or configuring the tenant store itself** — use configure-multi-tenancy (this skill only routes an existing tenant to a database).
- **Unit-of-work / transaction handling** — use manage-units-of-work.

## How it works

### The Default connection string

`Default` is the fallback. If a module has no connection string of its own, ABP uses `Default`. The layered startup template ships with only `Default`, so all modules share one database.

```json
"ConnectionStrings": {
  "Default": "Server=localhost;Database=MyMainDb;Trusted_Connection=True;"
}
```

### Named connection strings per module

Give a module its own database by adding a named entry. The name matches the module's connection string name:

```json
"ConnectionStrings": {
  "Default": "Server=localhost;Database=MyMainDb;Trusted_Connection=True;",
  "AbpIdentity": "Server=localhost;Database=MyIdentityDb;Trusted_Connection=True;",
  "AbpPermissionManagement": "Server=localhost;Database=MyPermissionDb;Trusted_Connection=True;"
}
```

Pre-built modules expose their connection string name as a constant (e.g. `AbpOpenIddictDbProperties.ConnectionStringName` in the `Volo.Abp.OpenIddict` namespace — for older solutions on IdentityServer it's `AbpIdentityServerDbProperties`) — use the constant instead of a magic string.

### Bind a DbContext to a connection string name

Annotate the `DbContext` (and its interface, if any) with `[ConnectionStringName]`. ABP then resolves that named connection string for this context. Applies to both EF Core and MongoDB:

```csharp
[ConnectionStringName("MyModule")]
public class MyModuleDbContext
    : AbpDbContext<MyModuleDbContext>, IMyModuleDbContext
{
}
```

### Grouping modules into one database

Instead of repeating the same connection string for several modules, map them to a shared database via `AbpDbConnectionOptions.Databases` in your module's `ConfigureServices`:

```csharp
Configure<AbpDbConnectionOptions>(options =>
{
    options.Databases.Configure("MySecondaryDb", db =>
    {
        db.MappedConnections.Add("AbpIdentity");
        db.MappedConnections.Add("AbpOpenIddict");
        db.MappedConnections.Add("AbpPermissionManagement");
    });
});
```

Then `appsettings.json` only needs the grouped name:

```json
"ConnectionStrings": {
  "Default": "Server=localhost;Database=MyMainDb;Trusted_Connection=True;",
  "MySecondaryDb": "Server=localhost;Database=MySecondaryDb;Trusted_Connection=True;"
}
```

You can also set/override connection strings in code (options pattern):

```csharp
Configure<AbpDbConnectionOptions>(options =>
{
    options.ConnectionStrings.Default = "...";
    options.ConnectionStrings["AbpPermissionManagement"] = "...";
});
```

**Resolution order:** ABP looks for (1) the module-specific connection string, then (2) a database mapping, then (3) falls back to `Default`.

### IConnectionStringResolver

Whenever ABP needs a connection string it calls `IConnectionStringResolver` (from `Volo.Abp.Data`):

```csharp
public interface IConnectionStringResolver
{
    Task<string> ResolveAsync(string? connectionStringName = null);

    [Obsolete("Use ResolveAsync method.")]
    string Resolve(string? connectionStringName = null);
}
```

Use `ResolveAsync` — `Resolve` is obsolete. Two built-in implementations:

- `DefaultConnectionStringResolver` — resolves from `AbpDbConnectionOptions` using the rules above.
- `MultiTenantConnectionStringResolver` — for multi-tenant apps; layers tenant-specific resolution on top of `DefaultConnectionStringResolver` and reads tenant connection strings from `ITenantStore`. If there is no current tenant, or the tenant defined no connection strings, it falls back entirely to the base (`DefaultConnectionStringResolver`) logic.

### Tenant-specific databases (per-tenant routing)

In a multi-tenant SaaS app, `MultiTenantConnectionStringResolver` routes each tenant to its own database automatically. For the current tenant it looks up the tenant's connection strings in the tenant store and resolves in this order:

- **Requesting the default connection** (`connectionStringName` null or `Default`): the tenant's own `Default` if set, otherwise the global `Default`.
- **Requesting a named connection**: (1) the tenant's connection string for that exact name, then (2) if that name maps to a grouped database the tenant is allowed to use, the tenant's connection string for the mapped database name, then (3) the tenant's own `Default`, and only then (4) fall back to the base `DefaultConnectionStringResolver` (global named → database mapping → global `Default`).

So a named request does **not** simply fall back to `Default` — it walks the tenant-specific chain first. Configure a tenant's connection string in the tenant management UI/data so its requests hit a separate database. See the multi-tenancy docs for using separate databases per tenant.

### Custom resolution

If you need custom logic to pick a connection string, implement `IConnectionStringResolver` (optionally deriving from one of the built-ins) and replace the registration via ABP's dependency injection system.

## Validation

- Confirm each module resolves to the intended database: a named entry present in `appsettings.json` wins over `Default`; a module with no named entry falls back to `Default`.
- After grouping modules, confirm the mapped modules all resolve to the grouped database name (e.g. `MySecondaryDb`).
- For multi-tenancy, sign in as a tenant that defines its own connection string and confirm its requests hit the separate database, while a tenant without one falls back to the global `Default`.

## Common Pitfalls

- **Use the module's connection-string-name constant, not a magic string** (e.g. `AbpOpenIddictDbProperties.ConnectionStringName`), so a rename in the module doesn't silently break resolution.
- **`Resolve` is obsolete** — always call `ResolveAsync`.
- **A named request does not simply fall back to `Default`** under multi-tenancy — `MultiTenantConnectionStringResolver` walks the full tenant-specific chain (exact name → mapped database → tenant Default → global) before the global `Default`.
- **Forgetting `[ConnectionStringName]`** on a `DbContext` (and its interface) leaves it resolving `Default` instead of its intended named database.
