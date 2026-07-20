---
name: model-domain-aggregates
description: >
  Model an ABP domain layer using DDD building blocks: entities, aggregate roots, value objects, domain services, specifications, and domain events.
  USE FOR: designing entities and aggregate roots (AggregateRoot with a typed key, GUID ids via IGuidGenerator, encapsulated invariants), immutable value objects (ValueObject + GetAtomicValues), domain services (DomainService, Manager suffix), reusable filters with the Specification base class, raising local/distributed domain events (AddLocalEvent / AddDistributedEvent) from an aggregate.
  DO NOT USE FOR: choosing which project a domain type lives in or overall solution layering (use layered-architecture); wiring the module class, [DependsOn], or DI registration (use define-application-modules); repository implementations and data-store specifics (use ef-core-integration or mongodb-integration); mapping entities to DTOs (use map-objects-and-dtos).
license: MIT
---

# Modeling the ABP Domain

The domain layer holds your business objects and core rules. ABP provides base classes for the standard DDD building blocks: entities, aggregate roots, value objects, domain services, and specifications. ABP does not force DDD, but makes these patterns easier to apply.

## When to Use

- Designing entities (`Entity<TKey>`) and aggregate roots (`AggregateRoot<TKey>`) with encapsulated invariants.
- Choosing GUID keys generated via `IGuidGenerator`.
- Modeling immutable value objects (`ValueObject` + `GetAtomicValues()`).
- Writing domain services (`DomainService`) for cross-aggregate or service-dependent logic.
- Building reusable, composable filters with `Specification<T>`.
- Raising local or distributed domain events from an aggregate.

## When Not to Use

- **Choosing which project a domain type lives in / overall layering** — use the layered-architecture skill.
- **Wiring the module class, `[DependsOn]`, or DI registration** — use the define-application-modules skill.
- **Repository implementations and data-store specifics** — use the ef-core-integration or mongodb-integration skill.
- **Mapping entities to DTOs** — use the map-objects-and-dtos skill.

## How it works

### Entities & Aggregate Roots

Entities derive from `Entity<TKey>` (namespace `Volo.Abp.Domain.Entities`) and get an `Id` of the given key type. Aggregate roots derive from `AggregateRoot<TKey>`, which extends `Entity<TKey>`. Only aggregate roots get default repositories by default.

`AggregateRoot` (and `AggregateRoot<TKey>`) implement `IHasExtraProperties` (an `ExtraProperties` dictionary → `GetProperty`/`SetProperty`) and `IHasConcurrencyStamp` (a `ConcurrencyStamp` set to a new GUID in the constructor for optimistic concurrency). If you don't want those, derive from `BasicAggregateRoot<TKey>` instead.

**GUID key best practices:**

- Add a public constructor taking the required data plus the id, and a `protected` empty constructor (used by the ORM on materialization).
- Never use `Guid.NewGuid()` for the id — pass an id created by the `IGuidGenerator` service (sequential GUIDs, better for clustered indexes). If you don't set an id, ABP sets it on save.
- Give properties `protected` setters and mutate state through methods so the aggregate stays valid.

```csharp
public class Order : AggregateRoot<Guid>
{
    public virtual string ReferenceNo { get; protected set; }
    public virtual int TotalItemCount { get; protected set; }
    public virtual List<OrderLine> OrderLines { get; protected set; }

    protected Order() { } // for the ORM

    public Order(Guid id, string referenceNo)
    {
        Check.NotNull(referenceNo, nameof(referenceNo));
        Id = id;
        ReferenceNo = referenceNo;
        OrderLines = new List<OrderLine>();
    }

    public void AddProduct(Guid productId, int count)
    {
        if (count <= 0)
        {
            throw new ArgumentException("Count must be positive!", nameof(count));
        }

        var line = OrderLines.FirstOrDefault(ol => ol.ProductId == productId);
        if (line == null)
        {
            OrderLines.Add(new OrderLine(Id, productId, count));
        }
        else
        {
            line.ChangeCount(line.Count + count);
        }

        TotalItemCount += count;
    }
}
```

The aggregate root owns its sub-entities: work with `OrderLine` only through `Order` (e.g. its constructor is `internal`). Reference other aggregate roots by `Id`, not navigation property. For audited entities, prefer the ready base classes: `CreationAuditedAggregateRoot<TKey>`, `AuditedAggregateRoot<TKey>`, `FullAuditedAggregateRoot<TKey>` (and non-generic composite-key variants).

For composite keys, derive from the non-generic `Entity` / `AggregateRoot` and override `GetKeys()`.

### Aggregate boundaries & size

Keep aggregates **small**. An aggregate is loaded and saved as one unit, so a large object
graph is slow to read and write. Set the boundary from: which objects are used together,
load/save cost, and where you need transactional consistency.

- Most aggregate roots have **no** sub-collections — reference related aggregates by id.
- Judge the boundary from the consistency/invariant scope, the load/save cost, and
  concurrency — not a fixed item count. If a sub-collection grows unbounded (hundreds or
  more in your measured workload), that's a sign to promote that child to its own aggregate
  root referenced by id rather than loading it as part of the parent.
- Example: a `Role` should not hold a `Users` collection (a role may have thousands of
  users). Model the small side (`User.Roles`) or a separate join aggregate instead.

### Load and save as a single unit

Change an aggregate by loading the whole thing, mutating it through its methods, and
saving it back — not by issuing partial child updates:

```csharp
public async Task AddCommentAsync(Guid issueId, string text)
{
    var issue = await _issueRepository.GetAsync(issueId, includeDetails: true); // load the whole aggregate
    issue.AddComment(CurrentUser.GetId(), text);          // business rules run on the in-memory graph
    await _issueRepository.UpdateAsync(issue);            // save the whole aggregate as one operation
}
```

Load the aggregate (rather than `INSERT`-ing a child row directly) so its methods can
enforce their rules — e.g. "no comments on a locked issue" needs the issue's state in
memory. For EF Core, configure the aggregate's details so the repository loads them by
default (or pass `includeDetails`); MongoDB loads the whole document naturally. Always
call `UpdateAsync` for a changed entity to stay database-provider independent — EF Core's
change tracking would auto-save, but MongoDB would not.

### Value Objects

Value objects (namespace `Volo.Abp.Domain.Values`) have no `Id`; two instances are equal when their values are equal. Derive from `ValueObject` and implement `GetAtomicValues()`; design them **immutable**.

```csharp
public class Address : ValueObject
{
    public Guid CityId { get; private set; }
    public string Street { get; private set; }
    public int Number { get; private set; }

    private Address() { }

    public Address(Guid cityId, string street, int number)
    {
        CityId = cityId;
        Street = street;
        Number = number;
    }

    protected override IEnumerable<object> GetAtomicValues()
    {
        yield return Street;
        yield return CityId;
        yield return Number;
    }
}
```

Compare with `address1.ValueEquals(address2)`. Properties that make up a value object should form one conceptual whole (e.g. keep CityId/Street/Number together, not spread across an entity).

### Domain Services

Use a domain service when core logic depends on other services (repositories, etc.) or spans more than one aggregate. Derive from `DomainService` (namespace `Volo.Abp.Domain.Services`) or implement `IDomainService`. ABP auto-registers it as **transient**; base properties like `ILogger` and `IGuidGenerator` are available without manual injection. Name it with a `Manager` (preferred) or `Service` suffix.

```csharp
public class IssueManager : DomainService
{
    private readonly IRepository<Issue, Guid> _issueRepository;

    public IssueManager(IRepository<Issue, Guid> issueRepository)
    {
        _issueRepository = issueRepository;
    }

    public async Task AssignAsync(Issue issue, AppUser user)
    {
        var count = await _issueRepository.CountAsync(i => i.AssignedUserId == user.Id);
        if (count >= 3)
        {
            throw new IssueAssignmentException(user.UserName);
        }

        issue.AssignedUserId = user.Id;
    }
}
```

Domain services take/return domain objects (entities, value objects) and are called from application services or other domain services — never from the presentation layer directly. Keep write access tight (e.g. `internal set` on the property the manager controls).

### Specifications

Specifications define named, reusable, composable, testable filters. Install `Volo.Abp.Specifications`, derive from `Specification<T>` (namespace `Volo.Abp.Specifications`) and override `ToExpression()`.

```csharp
public class Age18PlusCustomerSpecification : Specification<Customer>
{
    public override Expression<Func<Customer, bool>> ToExpression()
        => c => c.Age >= 18;
}
```

Use `spec.IsSatisfiedBy(customer)` for a single object, or pass the spec (or `spec.ToExpression()`) to a repository query — it translates to SQL:

```csharp
var queryable = await _customerRepository.GetQueryableAsync();
var query = queryable.Where(new Age18PlusCustomerSpecification());
```

Compose with `And`, `Or`, `Not`, `AndNot`, or subclass `AndSpecification<T>` for a named combination. Use specifications for business-meaningful filters; for reporting or ad-hoc queries just use plain `IQueryable`/LINQ.

### Domain Events on Aggregate Roots

Aggregate roots can publish events. Raise a **local** event (in-process, same transaction) or a **distributed** event (crosses service boundaries) from inside the aggregate:

```csharp
public void SetAsCompleted()
{
    IsCompleted = true;
    AddLocalEvent(new OrderCompletedEto { OrderId = Id });
    AddDistributedEvent(new OrderCompletedEto { OrderId = Id });
}
```

ABP publishes these events when the aggregate is saved through a repository. Use local events for in-process reactions and distributed events for other microservices/apps.

## Validation

- Aggregate root → `AggregateRoot<TKey>` (or `BasicAggregateRoot<TKey>` without extra props/concurrency); use `IGuidGenerator`, `protected` setters, protected empty ctor.
- Value object → `ValueObject` + `GetAtomicValues()`, immutable; compare via `ValueEquals`.
- Cross-aggregate / service-dependent logic → `DomainService` (`Manager` suffix).
- Reusable business filter → `Specification<T>` + `ToExpression()`; compose with And/Or/Not.
- Raise `AddLocalEvent` / `AddDistributedEvent` from the aggregate to signal state changes — confirm they fire when the aggregate is saved through a repository.

## Common Pitfalls

- **Using `Guid.NewGuid()` for aggregate ids** — always pass an id from `IGuidGenerator` (sequential GUIDs) or let ABP set it on save.
- **Public property setters** — give `protected` setters and mutate through methods so invariants hold.
- **Forgetting the `protected` empty constructor** — the ORM needs it for materialization.
- **Referencing other aggregate roots by navigation property** — reference by `Id` instead.
- **Mutable value objects** — design them immutable and compare with `ValueEquals`.
- **Calling domain services from the presentation layer** — they should be called from application services or other domain services only.
- **Large aggregates / unbounded sub-collections** — keep aggregates small; when a child collection can grow unbounded, promote it to its own aggregate root referenced by id (judge by consistency scope and load/save cost, not a fixed item count).
- **Partial updates that bypass the aggregate** — load the whole aggregate, mutate through its methods, then `UpdateAsync`, so its invariants are enforced.
