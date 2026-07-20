---
name: use-abp-repositories
description: "Consume ABP's IRepository from application/domain code — the standard method surface, eager loading, provider-neutral querying, tracking, and bulk/direct operations. USE FOR: choosing IRepository / IBasicRepository / IReadOnlyRepository / keyless repositories, GetAsync vs FindAsync not-found semantics, GetListAsync / GetPagedListAsync / GetCountAsync, WithDetailsAsync eager loading (templates don't rely on lazy loading), GetQueryableAsync + IAsyncQueryableExecuter for provider-neutral async LINQ, DisableTracking / [DisableEntityChangeTracking], bulk InsertMany/UpdateMany/DeleteManyAsync, DeleteDirectAsync, HardDeleteAsync, not leaking IQueryable to remote callers. DO NOT USE FOR: defining a custom repository interface + its EF Core / MongoDB implementation (ef-core-integration / mongodb-integration); where repo interfaces live across layers (layered-architecture); data filters / soft-delete (apply-data-filters); optimistic concurrency (handle-optimistic-concurrency)."
license: MIT
---

# Use ABP Repositories

A repository is ABP's abstraction for querying and persisting an aggregate root, provider-independent — the default generic `IRepository` is implemented by a data-access provider (EF Core, MongoDB, and the in-memory MemoryDb used in tests; the list isn't fixed). (Dapper is *not* a default-repository provider: ABP's Dapper integration is a custom `DapperRepository` layered on EF Core for hand-written SQL — see **query-with-dapper**.) This skill is about **consuming** an entity's `IRepository<TEntity, TKey>` — the method surface, eager loading, provider-neutral querying, tracking, and bulk operations. **Defining** a custom repository interface and its EF Core/MongoDB implementation is a different task — see **ef-core-integration** / **mongodb-integration**.

**Final application vs. reusable module — pick before you inject.** In a **final application** you can inject and use the default generic `IRepository<TEntity, TKey>` directly; that's what this skill shows. In a **reusable module** you publish for others, follow ABP's module best practice instead: define a **custom repository interface per aggregate root in the Domain layer**, deriving from `IBasicRepository<TEntity, TKey>` (not the full `IRepository`), and keep `GetQueryableAsync` / `IQueryable` out of the module's public surface — expose only the query methods the module needs. Define that interface + its provider implementation via **ef-core-integration** / **mongodb-integration**. The method surface, eager loading, tracking, and bulk guidance below applies to both.

Inject the repository for your aggregate root; the default is registered automatically:

```csharp
public class BookManager : IDomainService
{
    private readonly IRepository<Book, Guid> _bookRepository;
    public BookManager(IRepository<Book, Guid> bookRepository) => _bookRepository = bookRepository;
}
```

## When to Use

- Calling repository methods (`GetAsync`, `FindAsync`, `GetListAsync`, `InsertAsync`, …) on an aggregate.
- Eager-loading sub-collections/navigations with `WithDetailsAsync` (templates don't rely on lazy loading).
- Querying with `GetQueryableAsync` and executing async **without** leaking a provider (`IAsyncQueryableExecuter`).
- Choosing a read-only or basic repository variant, or controlling change tracking.
- Bulk insert/update/delete, direct delete, or hard-deleting a soft-delete entity.

## When Not to Use

- **Defining a custom repository interface + implementation** (`EfCoreRepository<…>`, `MongoDbRepository<…>`, `GetDbSetAsync`/`GetCollectionAsync`) — use **ef-core-integration** / **mongodb-integration**.
- **Where repository interfaces belong across layers** and `AddDefaultRepositories` — use **layered-architecture**.
- **Soft-delete / multi-tenant / custom data filters** and toggling them — use **apply-data-filters**.
- **Optimistic concurrency (`IHasConcurrencyStamp`, `AbpDbConcurrencyException`)** — use **handle-optimistic-concurrency**.

## Choosing a repository interface

| Interface | Gives you | Use when |
| --- | --- | --- |
| `IRepository<TEntity, TKey>` | Full surface: `IQueryable` access + all reads + writes | The default; the entity has a single primary key. |
| `IRepository<TEntity>` | Same but **no** id-based methods (`GetAsync(id)` etc.) | The entity has a composite/no single key. |
| `IReadOnlyRepository<TEntity, TKey>` | Reads + `IQueryable`, **no** write methods | A service that must not mutate; on EF Core it also **disables change tracking** for its results. |
| `IBasicRepository<TEntity, TKey>` | Reads by id/list + writes, **no** `IQueryable` | You don't want to depend on LINQ/`IQueryable` (e.g. a provider without queryable support). |
| `IReadOnlyBasicRepository<TEntity, TKey>` | Basic reads only | Minimal read dependency, no LINQ. |

Prefer the **narrowest** interface a caller needs. `IReadOnlyRepository` is not just intent — on EF Core its query results are **not change-tracked**, which is faster for pure reads.

## Standard methods & `GetAsync` vs `FindAsync`

```csharp
Book book   = await _bookRepository.GetAsync(id);    // throws EntityNotFoundException if missing
Book? maybe = await _bookRepository.FindAsync(id);   // returns null if missing
List<Book> all   = await _bookRepository.GetListAsync();
long       count = await _bookRepository.GetCountAsync();
List<Book> page  = await _bookRepository.GetPagedListAsync(skipCount: 0, maxResultCount: 10, sorting: "Name");
```

- **`GetAsync` throws `EntityNotFoundException`** (surfaces as HTTP 404 through ABP) — use it when absence is an error.
- **`FindAsync` returns `null`** — use it when absence is a normal case you handle.
- Predicate overloads exist too: `GetAsync(x => x.Name == name)`, `FindAsync(x => …)`.
- `EnsureExistsAsync(id)` / `EnsureExistsAsync(predicate)` throws `EntityNotFoundException` when nothing matches — a guard when you only need to assert existence, not load the entity.

## Eager loading — templates don't rely on lazy loading

ABP's startup templates don't enable EF Core lazy loading, so navigations/sub-collections are **not** auto-loaded — load them explicitly. (You *can* opt into lazy loading with EF Core's `UseLazyLoadingProxies()`, but the templates and repository best practices assume explicit/eager loading; ABP doesn't forbid it.) This is the single most common repository gotcha.

- `GetAsync(id, includeDetails: true)` (the default `includeDetails` is `true` on the id overloads) loads the entity's **default details**, defined per-entity by a `DefaultWithDetailsFunc` in the EF Core repository registration.
- For a query, start from a details-including queryable:

```csharp
// default details for the entity
IQueryable<Book> q1 = await _bookRepository.WithDetailsAsync();
// specific navigations only
IQueryable<Book> q2 = await _bookRepository.WithDetailsAsync(b => b.Chapters, b => b.Author);
```

Only eager-load within the **aggregate boundary** — a repository loads its own aggregate's sub-entities, not other aggregates. To combine aggregates, query each and join in memory, or use a dedicated read model.

## Querying: `GetQueryableAsync` + provider-neutral async execution

`GetQueryableAsync()` returns an `IQueryable<TEntity>` you can compose with LINQ. The trap: `IQueryable`'s async operators (`ToListAsync`, `FirstOrDefaultAsync`, …) are **provider-specific** — the EF Core ones live in `Microsoft.EntityFrameworkCore`. Referencing them from Domain/Application code couples those layers to EF Core.

Use ABP's `IAsyncQueryableExecuter` instead, which resolves to the active provider. In an `ApplicationService` / `DomainService` it's the `AsyncExecuter` property; elsewhere inject `IAsyncQueryableExecuter` (namespace `Volo.Abp.Linq`):

```csharp
var queryable = await _bookRepository.GetQueryableAsync();
var query = queryable.Where(b => b.Price > 100).OrderBy(b => b.Name);

List<Book> list = await AsyncExecuter.ToListAsync(query);      // in an app/domain service
Book? first     = await AsyncExecuter.FirstOrDefaultAsync(query);
int total       = await AsyncExecuter.CountAsync(query);
```

A queryable must be **materialized inside a unit of work** (a request scope is one) — the `DbContext`/session backing it is disposed when the UoW ends. Don't return a raw `IQueryable` out of that scope. If a caller needs no-tracking and provider-independence, prefer an `IReadOnlyRepository` or a custom repository method over exposing the queryable.

## Change tracking

On EF Core, entities read for update are change-tracked so `SaveChanges` persists your edits. For read-heavy paths that don't mutate, turn tracking off:

- `using (_bookRepository.DisableTracking()) { … }` (and `EnableTracking()`) scope a block.
- `[DisableEntityChangeTracking]` on a method disables tracking for its duration.
- An `IReadOnlyRepository` already returns untracked results.

Don't disable tracking around code that expects its edits to be saved by the UoW — untracked entities won't be persisted unless you call `UpdateAsync` explicitly.

## Bulk & direct operations

```csharp
await _bookRepository.InsertManyAsync(books, autoSave: true);
await _bookRepository.UpdateManyAsync(books);
await _bookRepository.DeleteManyAsync(books);              // or DeleteManyAsync(ids)
await _bookRepository.DeleteDirectAsync(b => b.IsObsolete); // bulk delete by predicate
```

`UpdateManyAsync` / `DeleteManyAsync` handle optimistic concurrency **per provider**, not uniformly — don't assume bulk means "no `ConcurrencyStamp` check". MongoDB, for one, re-stamps and re-checks soft-deleted entities and throws an optimistic-concurrency exception when the stamp no longer matches; verify the behavior for the provider you target rather than assuming a concurrent edit goes undetected.

`DeleteDirectAsync(predicate)` is **provider-dependent** — the base method is `abstract`, so there is no shared "bypass" or fallback guarantee:

- **EF Core** (`ExecuteDeleteAsync`) and **MongoDB** (`DeleteManyAsync`) run a **single set-based physical delete** that skips the pipeline — no entity loading, no change tracking, no domain/entity events, no concurrency check — and it **hard-deletes even `ISoftDelete` entities** (no soft-delete conversion). Efficient for large deletes.
- **MemoryDb** routes through `DeleteAsync`, so soft-delete, events, and auditing **do** run — the opposite of the set-based providers.
- A **custom provider** guarantees neither; check its implementation.

So don't treat direct delete as a portable "bypass". On EF Core / MongoDB use it only when the set-based hard delete and skipped side effects are genuinely wanted; otherwise load-and-`DeleteAsync` so soft-delete, events, and auditing run.

## Hard delete vs soft delete

An entity implementing `ISoftDelete` is not physically removed — `DeleteAsync` sets `IsDeleted = true` and ABP's soft-delete data filter hides it from later queries (see **apply-data-filters**). To remove it permanently, use the `HardDeleteAsync` repository extension:

```csharp
await _bookRepository.HardDeleteAsync(b => b.Id == id); // permanent, ignores soft-delete
```

## Don't leak `IQueryable` to remote callers

`IQueryable` and repositories are a Domain/Application tool. Never return `IQueryable` (or expose it via an `IQueryable`-typed API/OData surface) across a remote/HTTP boundary — materialize inside the UoW and return DTOs or a paged `List`. Application services return DTOs; repositories return entities; neither returns a live queryable.

## Validation

- Missing navigation data on a returned entity almost always means eager loading wasn't requested — add `WithDetailsAsync(...)` or `includeDetails: true`, and confirm the entity's `DefaultWithDetailsFunc` covers what you expect.
- A "cannot access a disposed context" / closed-session error when enumerating a query means the queryable escaped its unit of work — materialize it (via `AsyncExecuter`) before the scope ends.
- If edits aren't saved, check you didn't read them through a no-tracking path (`IReadOnlyRepository` / `DisableTracking`) without an explicit `UpdateAsync`.

## Common Pitfalls

- **Assuming navigations auto-load** — lazy loading isn't enabled by default; use `WithDetailsAsync` / `includeDetails: true` (or opt into `UseLazyLoadingProxies()`).
- **Using EF Core's `ToListAsync`/`FirstOrDefaultAsync` on the queryable** — that couples the layer to EF Core; use `AsyncExecuter` / `IAsyncQueryableExecuter`.
- **`GetAsync` where you meant `FindAsync`** — `GetAsync` throws on missing; `FindAsync` returns null.
- **`DeleteDirectAsync` on EF Core / MongoDB for entities that need events/soft-delete/audit** — the set-based providers bypass all of them (MemoryDb doesn't — see the provider-dependent note above); load-and-`DeleteAsync` instead.
- **Expecting `HardDeleteAsync` behavior from `DeleteAsync` on a soft-delete entity** — the latter only flags `IsDeleted`.
- **Returning or exposing `IQueryable` from an app service / API** — materialize to DTOs inside the UoW.
- **Reusing a queryable after the unit of work ends** — the backing context/session is gone.

## See also

- Repositories: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/architecture/domain-driven-design/repositories.md`
- Repository best practices: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/architecture/best-practices/repositories.md`
