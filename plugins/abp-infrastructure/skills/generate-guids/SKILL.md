---
name: generate-guids
description: "ABP IGuidGenerator entity IDs and sequential GUID layout for the active database provider. USE FOR: IGuidGenerator.Create; SequentialGuidGenerator; SimpleGuidGenerator; AbpSequentialGuidGeneratorOptions.DefaultSequentialGuidType; SequentialAtEnd / SequentialAsString / SequentialAsBinary. DO NOT USE FOR: cache keys and invalidation (cache-entities); cryptographic tokens or secrets (encrypt-strings); schema and repository design."
license: MIT
---

# Generate GUIDs in ABP

Use `IGuidGenerator.Create()` for entity IDs instead of `Guid.NewGuid()`. ABP's default `SequentialGuidGenerator` preserves GUID uniqueness while placing a timestamp component where the target database can order it efficiently.

## When to Use

- Create a `Guid` before constructing a new entity or aggregate root.
- Keep entity creation independent of the database provider.
- Select the sequential byte layout for SQL Server, MySQL, PostgreSQL, or Oracle.
- Use the pre-injected `GuidGenerator` property on ABP application/domain service base classes.

## When Not to Use

- **Create cache keys or coordinate cache invalidation** — use cache-entities.
- **Create password reset tokens, API secrets, or cryptographic nonces** — GUID generation is not a token-protection workflow.
- **Choose entity key types or model database indexes generally** — this skill only covers ABP GUID generation.

## How it works

### Generate IDs at the creation boundary

`IGuidGenerator` exposes only `Guid Create()`:

```csharp
public class ProductAppService : ApplicationService
{
    private readonly IRepository<Product, Guid> _productRepository;

    public ProductAppService(IRepository<Product, Guid> productRepository)
    {
        _productRepository = productRepository;
    }

    public async Task CreateAsync(string name)
    {
        var product = new Product(GuidGenerator.Create(), name);
        await _productRepository.InsertAsync(product);
    }
}
```

Outside an ABP base class, inject `IGuidGenerator`. Pass the generated ID into the entity constructor; do not make entity constructors call a service locator or `Guid.NewGuid()`.

### Understand the two implementations

- `SequentialGuidGenerator` implements `IGuidGenerator` and `ITransientDependency`; it is the default DI implementation. It uses 10 cryptographically random bytes plus a six-byte UTC millisecond timestamp.
- `SimpleGuidGenerator.Instance` implements `IGuidGenerator` by returning `Guid.NewGuid()`. ABP base classes use it as a fallback only when no `IGuidGenerator` service can be resolved.

Sequential GUIDs address the insert cost of random GUID clustered keys: inserting unrelated random values can require database index page reordering. They do not make insertion order a business-level ordering contract; store an explicit timestamp or sequence when ordering matters.

### Choose the database-specific layout

`AbpSequentialGuidGeneratorOptions.DefaultSequentialGuidType` is nullable and defaults to `null`. `GetDefaultSequentialGuidType()` falls back to `SequentialAtEnd`.

| Value | Sequential representation | Database mapping |
| --- | --- | --- |
| `SequentialAtEnd` | Timestamp at the end of the GUID data | SQL Server; fallback default |
| `SequentialAsString` | Sequential when formatted with `Guid.ToString()` | MySQL and PostgreSQL |
| `SequentialAsBinary` | Sequential when formatted with `Guid.ToByteArray()` | Oracle |

The matching ABP EF Core provider modules set the value only when it is still `null`. Manual configuration is normally unnecessary when using those packages:

```csharp
using Volo.Abp.Guids;

Configure<AbpSequentialGuidGeneratorOptions>(options =>
{
    options.DefaultSequentialGuidType = SequentialGuidType.SequentialAsString;
});
```

Configure it manually only when the actual database storage and comparison behavior requires an override.

## Validation

- Resolve `IGuidGenerator` and confirm the concrete implementation is `SequentialGuidGenerator` in the application.
- Generate a large sample and assert uniqueness.
- Verify the configured `SequentialGuidType` matches the real database provider and GUID column representation.
- Insert representative rows and inspect index behavior with the production database engine when performance is the reason for the change.
- Confirm entity creation paths use `IGuidGenerator`, including data seeders and imports.

## Common Pitfalls

- **Using `Guid.NewGuid()` for entity IDs** — it bypasses ABP's sequential strategy.
- **Choosing a layout by intuition** — string, binary, and SQL Server GUID ordering differ.
- **Overriding an EF Core provider's correct default unnecessarily** — provider modules configure the matching type when the option is null.
- **Using `SimpleGuidGenerator` as the normal application service** — it intentionally delegates to `Guid.NewGuid()`.
- **Sorting by generated GUID as business chronology** — the generator contains a timestamp component but does not define a domain ordering contract.
