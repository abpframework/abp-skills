---
name: handle-optimistic-concurrency
description: >
  Enable and handle ABP optimistic concurrency control so concurrent updates to the same record are detected and rejected.
  USE FOR: enabling concurrency with IHasConcurrencyStamp/ConcurrencyStamp, deriving from aggregate root base classes to get it for free, flowing the stamp through output and update DTOs, handling AbpDbConcurrencyException when two users update the same record.
  DO NOT USE FOR: EF-Core-specific mapping/change tracking (use ef-core-integration), MongoDB provider setup (use mongodb-integration), unit-of-work flush/transaction control (use manage-units-of-work), general validation/error surfacing (use handle-validation-and-errors).
license: MIT
---

# Handle Optimistic Concurrency in ABP

ABP's concurrency check uses **optimistic concurrency control**: users can attempt to update the same record without being blocked up front. When one update wins, the others are rejected because the record has changed underneath them and must be re-read before retrying.

## When to Use

- You need to detect and reject concurrent updates to the same record instead of silently overwriting.
- You want to enable concurrency control on an entity via `IHasConcurrencyStamp` / `ConcurrencyStamp`.
- You want concurrency for free by deriving from an aggregate root base class.
- You need to flow the stamp from the read DTO back through the update DTO so a stale client is rejected.
- You need to handle or surface `AbpDbConcurrencyException`.

## When Not to Use

- **EF-Core-specific mapping or change tracking** — use ef-core-integration.
- **MongoDB provider setup** — use mongodb-integration (this skill only notes provider-specific stamp behavior).
- **Unit-of-work flush / transaction control** — use manage-units-of-work.
- **General validation and user-facing error handling** — use handle-validation-and-errors.

## How it works

### `IHasConcurrencyStamp`

Implement this interface (directly or indirectly) to enable concurrency control on an entity:

```csharp
public interface IHasConcurrencyStamp
{
    string ConcurrencyStamp { get; set; }
}
```

How ABP uses the stamp:

- On **create**, behavior is provider-specific. With **EF Core**, `AbpDbContext` runs `SetConcurrencyStampIfNull` on added entities, so a null `ConcurrencyStamp` is filled in automatically. With **MongoDB**, insert does **not** set the stamp — the aggregate root base classes work only because their constructor generates one. A plain `Entity<TKey>, IHasConcurrencyStamp` on MongoDB must initialize `ConcurrencyStamp` itself.
- On **update**, ABP compares the entity's current `ConcurrencyStamp` against the value stored in the database. If they **match**, it saves and ABP itself generates a **new** stamp (`Guid.NewGuid().ToString("N")` in framework code — not by the database). If they **mismatch**, it throws `AbpDbConcurrencyException`.

### Get it via a base class

The aggregate root base classes already implement `IHasConcurrencyStamp`, so deriving from any of these gives you concurrency control without implementing it yourself:

- `AggregateRoot`, `AggregateRoot<TKey>`
- `CreationAuditedAggregateRoot`, `CreationAuditedAggregateRoot<TKey>`
- `AuditedAggregateRoot`, `AuditedAggregateRoot<TKey>`
- `FullAuditedAggregateRoot`, `FullAuditedAggregateRoot<TKey>`

```csharp
public class Book : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; }
    //...
}
```

If your entity derives from a plain `Entity<TKey>`, implement the interface explicitly. On MongoDB, initialize the stamp yourself (EF Core fills a null stamp on insert, but MongoDB does not):

```csharp
public class Book : Entity<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = Guid.NewGuid().ToString("N");
    //...
}
```

### Flow the stamp through DTOs

The stamp only protects an update if the client sends back the stamp it last read. So expose it on the **output** DTO and require it on the **update** DTO:

```csharp
public class BookDto : EntityDto<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; }
    //...
}

public class UpdateBookDto : IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; }
    //...
}
```

In the application service's update method, copy the incoming stamp onto the entity **before** saving:

```csharp
public class BookAppService : ApplicationService, IBookAppService
{
    //...

    public virtual async Task<BookDto> UpdateAsync(Guid id, UpdateBookDto input)
    {
        var book = await BookRepository.GetAsync(id);

        book.ConcurrencyStamp = input.ConcurrencyStamp;

        // ...set the other input values...

        // autoSave: true flushes now, so the entity carries the new stamp
        await BookRepository.UpdateAsync(book, autoSave: true);

        return ObjectMapper.Map<Book, BookDto>(book);
    }
}
```

Because the client received `ConcurrencyStamp` in `BookDto` and sent the same value in `UpdateBookDto`, a second user editing a stale copy will send an old stamp, the comparison mismatches, and `AbpDbConcurrencyException` is thrown.

### Save changes to get the new stamp

The stamp is validated and the next one is generated by ABP framework code (`Guid.NewGuid().ToString("N")`), not by the database engine. When exactly the entity picks up the regenerated stamp is provider-specific. With **EF Core**, `UpdateConcurrencyStamp` runs at `SaveChanges` time, so inside a unit of work you must trigger a flush to read the new value — pass `autoSave: true` to `UpdateAsync`/`InsertAsync` (as above) or call `CurrentUnitOfWork.SaveChangesAsync()`; otherwise the entity holds the old stamp until the UOW completes. With **MongoDB**, `UpdateAsync` regenerates the stamp on the entity right before `ReplaceOneAsync`, independent of `autoSave`.

### Handling `AbpDbConcurrencyException`

`AbpDbConcurrencyException` lives in `Volo.Abp.Data` and derives from `AbpException`. You have two options:

1. **Let ABP handle it** — if you don't catch it, ABP surfaces a user-friendly error message automatically. This is the common case; often you don't write any catch at all.
2. **Handle it yourself** — catch it to run custom recovery, e.g. tell the user their copy is stale and reload:

```csharp
try
{
    await _bookAppService.UpdateAsync(id, input);
}
catch (AbpDbConcurrencyException)
{
    // The record changed since it was loaded.
    // Re-read the latest entity/DTO and let the user redo their edit.
}
```

Since resolving a conflict requires the caller to fetch the latest data and re-apply changes, the typical UX is: catch (or surface ABP's default message), reload the current record with its fresh `ConcurrencyStamp`, and let the user retry.

## Validation

- Confirm the entity implements `IHasConcurrencyStamp` (directly or via an aggregate root base class) and that both the output and update DTOs carry `ConcurrencyStamp`.
- Read a record, then update the same record twice with the *original* stamp: the first update succeeds, the second throws `AbpDbConcurrencyException`.
- With EF Core, after `UpdateAsync(book, autoSave: true)` verify the returned DTO's `ConcurrencyStamp` differs from the one sent in — proving the stamp regenerated.

## Common Pitfalls

- **MongoDB does not fill a null stamp on insert.** A plain `Entity<TKey>, IHasConcurrencyStamp` on MongoDB must initialize `ConcurrencyStamp` itself; EF Core fills it via `SetConcurrencyStampIfNull`, MongoDB does not.
- **Not flushing under EF Core leaves the old stamp.** `UpdateConcurrencyStamp` runs at `SaveChanges` time, so inside a UOW the entity keeps the old stamp until you pass `autoSave: true` or call `CurrentUnitOfWork.SaveChangesAsync()`.
- **Forgetting to copy `input.ConcurrencyStamp` onto the entity** before saving defeats the check — a stale client would silently overwrite the winner.
- **The new stamp comes from ABP framework code**, not the database (`Guid.NewGuid().ToString("N")`) — don't expect a DB-generated rowversion.
