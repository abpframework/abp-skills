---
name: layered-architecture
description: >
  Organize an ABP solution/module into DDD layers and decide which project a given type belongs in.
  USE FOR: laying out the *.Domain.Shared / *.Domain / *.Application.Contracts / *.Application / *.EntityFrameworkCore / *.MongoDB / *.HttpApi / *.HttpApi.Client / *.Web|*.Blazor projects, deciding whether an entity, aggregate root, repository interface/impl, domain service, or DTO belongs in Domain vs Application vs infrastructure, and understanding the one-way reference flow.
  DO NOT USE FOR: detailed domain modeling of aggregates, value objects, or specifications (use model-domain-aggregates); wiring the module class, [DependsOn], or DI (use define-application-modules); repository implementation details per data store (use ef-core-integration or mongodb-integration); writing application service logic (use application-services); DTO mapping mechanics (use map-objects-and-dtos).
license: MIT
---

# ABP Layered (DDD) Architecture

ABP structures a module/application into layers, each a separate .NET project. Put every type in the layer it belongs to — this keeps dependencies flowing one way (UI → Application → Domain, plus infrastructure providers).

## When to Use

- Laying out the projects of an ABP solution or module.
- Deciding which project an entity, aggregate root, repository interface/impl, domain service, or DTO belongs in.
- Understanding the one-way reference flow between layers.
- Placing auditing base classes, repository interfaces vs implementations, and DTOs correctly.

## When Not to Use

- **Detailed domain modeling** of aggregates, value objects, or specifications — use the model-domain-aggregates skill.
- **Wiring the module class, `[DependsOn]`, or DI** — use the define-application-modules skill.
- **Repository implementation details per data store** — use the ef-core-integration or mongodb-integration skill.
- **Writing application service logic** — use the application-services skill.
- **DTO mapping mechanics** — use the map-objects-and-dtos skill.

## How it works

### The projects/layers

| Project | Contains | References |
| --- | --- | --- |
| `*.Domain.Shared` | Constants, enums, shared error codes, localization resource, shared consts used by every layer | `Volo.Abp.Ddd.Domain.Shared`, `Volo.Abp.Validation` |
| `*.Domain` | Entities, aggregate roots, value objects, domain services, repository **interfaces**, domain events, business rules | Domain.Shared |
| `*.Application.Contracts` | DTOs, application service **interfaces** (`I...AppService`), permission definitions | Domain.Shared |
| `*.Application` | Application service **implementations**, Mapperly mappers / AutoMapper profiles | Application.Contracts, Domain |
| `*.EntityFrameworkCore` | `DbContext`, EF Core repository implementations, entity mappings | Domain |
| `*.MongoDB` | Mongo `DbContext`, Mongo repository implementations | Domain |
| `*.HttpApi` | Auto/API controllers exposing the app services over HTTP | Application.Contracts |
| `*.HttpApi.Client` | C# client proxies calling the remote HTTP API | Application.Contracts |
| `*.Web` / `*.Blazor` | UI (Razor Pages/MVC or Blazor), pages, view models | Non-tiered host: Application + EntityFrameworkCore (runs the app in-process). Tiered/separate client: HttpApi.Client (calls the API remotely). |

Rule of thumb: **interfaces + business types go in Domain/Contracts; implementations go in Application/infrastructure.**

### Entities & aggregate roots

Namespace `Volo.Abp.Domain.Entities` (and `.Auditing`). Prefer **`Guid` keys** for aggregate roots.

```csharp
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Entities.Auditing;

// A plain entity with a typed key
public class OrderLine : Entity<Guid>
{
    public string ProductName { get; set; }
    public int Quantity { get; set; }
    protected OrderLine() { }
}

// An aggregate root — the consistency boundary; repositories target these
public class Order : AggregateRoot<Guid>
{
    public string CustomerName { get; set; }
    protected Order() { }
    public Order(Guid id, string customerName) : base(id)
    {
        CustomerName = customerName;
    }
}
```

Auditing base classes add audit fields automatically (populated by ABP):

- `AuditedEntity<TKey>` / `AuditedAggregateRoot<TKey>` → `CreationTime`, `CreatorId`, `LastModificationTime`, `LastModifierId`.
- `FullAuditedAggregateRoot<TKey>` → the above plus soft-delete (`IsDeleted`, `DeletionTime`, `DeleterId`).
- `CreationAuditedEntity<TKey>` → creation fields only.

```csharp
public class Book : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; }
    public decimal Price { get; set; }
    protected Book() { }
    public Book(Guid id, string name) : base(id) { Name = name; }
}
```

Keep a `protected` parameterless constructor for the ORM/deserializer and expose a real constructor that enforces invariants.

### Repositories

Interfaces `IRepository<TEntity>` and `IRepository<TEntity, TKey>` live in `Volo.Abp.Domain.Repositories`. `AddDefaultRepositories()` auto-implements the generic repository for **aggregate roots** — you inject it directly, no custom class needed:

```csharp
public class BookManager : DomainService
{
    private readonly IRepository<Book, Guid> _bookRepository;
    public BookManager(IRepository<Book, Guid> bookRepository)
        => _bookRepository = bookRepository;
}
```

`IRepository<TEntity, TKey>` gives `GetAsync`, `FindAsync`, `InsertAsync`, `UpdateAsync`, `DeleteAsync`, `GetListAsync`, `GetQueryableAsync`, etc.

Default repositories are only registered for aggregate roots. To also get default repositories for non-aggregate-root entities, use `AddDefaultRepositories(includeAllEntities: true)`.

For non-trivial queries, declare a **custom repository interface in the Domain layer** and implement it in the EF Core / MongoDB layer:

```csharp
// *.Domain
public interface IBookRepository : IRepository<Book, Guid>
{
    Task<List<Book>> GetListByAuthorAsync(Guid authorId);
}
```

### Domain services

Use a `DomainService` (base class in `Volo.Abp.Domain.Services`) for business logic that spans multiple aggregates or needs repositories/other services — logic that doesn't naturally belong to a single entity.

```csharp
using Volo.Abp.Domain.Services;

public class IssueManager : DomainService
{
    private readonly IRepository<Issue, Guid> _issueRepository;
    public IssueManager(IRepository<Issue, Guid> issueRepository)
        => _issueRepository = issueRepository;

    public async Task<Issue> CreateAsync(string title)
    {
        // enforce cross-aggregate rules here (this is why it's a domain service), then
        // return the new entity — the application service persists it, so the domain
        // service doesn't save (see separate-domain-and-application-logic)
        if (await _issueRepository.AnyAsync(i => i.Title == title))
        {
            throw new BusinessException("IssueTracking:DuplicateIssueTitle");
        }

        return new Issue(GuidGenerator.Create(), title);
    }
}
```

Domain services are named `...Manager` by convention and are registered automatically (transient).

### Where DTOs live

DTOs belong in **`*.Application.Contracts`** (namespace pattern `Volo.Abp.Application.Dtos` provides base types). Never leak entities out of the application layer — application services accept and return DTOs. Handy base DTOs: `EntityDto<TKey>`, `AuditedEntityDto<TKey>`, `FullAuditedEntityDto<TKey>`, and request DTOs `PagedResultRequestDto`, `PagedAndSortedResultRequestDto`, plus `PagedResultDto<T>` / `ListResultDto<T>` for results.

## Validation

- Each type lands in the right project: interfaces + business types in Domain/Contracts; implementations in Application/infrastructure.
- Project references flow one way (UI → Application → Domain, plus infrastructure providers) — no reverse or cross-layer references.
- Repository interfaces live in `*.Domain`; their implementations live in `*.EntityFrameworkCore` / `*.MongoDB`.
- DTOs live in `*.Application.Contracts`; entities never leave the application layer.

## Common Pitfalls

- **Leaking entities out of the application layer** — application services must accept and return DTOs, not entities.
- **Putting repository implementations in the Domain layer** — interfaces go in `*.Domain`, implementations in `*.EntityFrameworkCore` / `*.MongoDB`.
- **Expecting default repositories for non-aggregate-root entities** — only aggregate roots get them unless you use `AddDefaultRepositories(includeAllEntities: true)`.
- **Omitting the `protected` parameterless constructor** — the ORM/deserializer needs it; keep a separate real constructor to enforce invariants.
- **Placing DTOs or app-service interfaces outside `*.Application.Contracts`** — that's where consumers and client proxies expect them.
