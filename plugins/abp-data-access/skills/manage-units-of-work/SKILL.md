---
name: manage-units-of-work
description: >
  Control ABP's Unit of Work — transaction and connection scope, explicit UOW scopes, the [UnitOfWork] attribute, and mid-scope SaveChangesAsync.
  USE FOR: starting explicit scopes with IUnitOfWorkManager.Begin, applying [UnitOfWork], choosing transactional vs non-transactional boundaries, calling SaveChangesAsync mid-scope, working with nested/RequiresNew/reserved scopes, reading IUnitOfWorkManager.Current, using OnCompleted/CompleteAsync/RollbackAsync.
  DO NOT USE FOR: defining a DbContext or repositories, or EF Core migrations (use ef-core-integration); MongoDB DbContext/repositories (use mongodb-integration); soft-delete/multi-tenant/custom query filters (use apply-data-filters); optimistic concurrency stamps (use handle-optimistic-concurrency); connection-string resolution (use configure-connection-strings).
license: MIT
---

# Manage ABP Units of Work

ABP's Unit of Work (UOW) controls the **database connection and transaction** scope. Once a UOW starts it creates an **ambient scope**: every database operation done inside it participates in one boundary and is committed on success or rolled back on exception, all together.

## When to Use

- Starting a UOW outside the conventions (background jobs, console apps, an inner scope) with `IUnitOfWorkManager.Begin`.
- Enabling/disabling a UOW or its transaction on a method/class with `[UnitOfWork]`.
- Choosing transactional vs non-transactional boundaries, or changing the global default.
- Flushing pending changes mid-scope with `SaveChangesAsync` (e.g. to read an auto-increment id).
- Running nested/`RequiresNew`/reserved scopes, or hooking `OnCompleted`.

## When Not to Use

- **Defining a DbContext, repositories, or EF Core migrations** — use the **ef-core-integration** skill.
- **MongoDB DbContext / repositories** — use **mongodb-integration**.
- **Soft-delete / multi-tenant / custom query filters** — use **apply-data-filters**.
- **Optimistic concurrency stamps** — use **handle-optimistic-concurrency**.
- **Connection-string resolution/configuration** — use **configure-connection-strings**.

## How it works

### When a UOW auto-completes (you usually don't touch it)

These method types are conventionally wrapped in a UOW and completed automatically when they return without throwing:

- ASP.NET Core MVC **controller actions**
- Razor **page handlers**
- **Application service** methods
- **Repository** methods

A UOW auto-begins for these **unless there is already a surrounding (ambient) UOW** — in that case the inner call silently participates in the outer one. So a repository called from an app service does not open its own UOW; it joins the app service's UOW. This is why you rarely start a UOW yourself.

#### Transactional or not (default behavior)

A UOW does not have to be transactional. By default:

- **HTTP GET** requests start a UOW but **no database transaction**.
- All other HTTP methods (POST/PUT/DELETE/PATCH/QUERY/...) start a UOW **with a transaction**, if the provider supports it — only GET is non-transactional by default. You can mark extra paths non-transactional via `AspNetCoreUnitOfWorkTransactionBehaviourProviderOptions.NonTransactionalUrls`.

Change the global default via `AbpUnitOfWorkDefaultOptions` in your module's `ConfigureServices`:

```csharp
Configure<AbpUnitOfWorkDefaultOptions>(options =>
{
    options.TransactionBehavior = UnitOfWorkTransactionBehavior.Disabled; // or Enabled / Auto
});
```

`AbpUnitOfWorkDefaultOptions` also exposes `Timeout` (`int?`) and `IsolationLevel` (`IsolationLevel?`).

### `[UnitOfWork]` attribute

Put `[UnitOfWork]` on a method or a class to enable/disable a UOW and control its transaction behavior. Interception rules: if you don't inject the service over an interface, the method must be `virtual`; only `async` methods (returning `Task`/`Task<T>`) are intercepted.

```csharp
public class MyService : ITransientDependency
{
    [UnitOfWork(IsTransactional = true)]
    public virtual async Task FooAsync() { /* transactional UOW scope */ }
}
```

Attribute properties (from `UnitOfWorkAttribute`):

- `IsTransactional` (`bool?`) — null means "decide by convention/config".
- `Timeout` (`int?`) — milliseconds.
- `IsolationLevel` (`IsolationLevel?`) — only meaningful when transactional.
- `IsDisabled` (`bool`) — prevent starting a UOW for this method/class.

```csharp
[UnitOfWork(IsDisabled = true)]
public virtual async Task NoUowAsync() { /* ... */ }
```

**Important:** if the method is called inside an ambient UOW, the attribute is **ignored** — the method just participates in the surrounding UOW. `[UnitOfWork]` only takes effect when it is the outermost scope.

### Starting a UOW explicitly: `IUnitOfWorkManager.Begin`

Inject `IUnitOfWorkManager` when you need a UOW outside the conventions (background jobs, console apps, or an inner scope). The convenient extension overload:

```csharp
public class MyService : ITransientDependency
{
    private readonly IUnitOfWorkManager _unitOfWorkManager;

    public MyService(IUnitOfWorkManager unitOfWorkManager)
    {
        _unitOfWorkManager = unitOfWorkManager;
    }

    public virtual async Task FooAsync()
    {
        using (var uow = _unitOfWorkManager.Begin(
            requiresNew: true, isTransactional: true))
        {
            // ... database operations ...
            await uow.CompleteAsync(); // must call, or it rolls back on dispose
        }
    }
}
```

`Begin(requiresNew = false, isTransactional = false, isolationLevel = null, timeout = null)`:

- `requiresNew` — `false` (default): if a surrounding UOW exists, `Begin` does **not** open a new one, it silently joins the existing UOW. `true`: ignore the ambient UOW and start a fresh, independent one (its own transaction).
- When you open a UOW manually via `Begin`, you own its completion: call `await uow.CompleteAsync()` before leaving the `using`. If you don't complete it, disposing rolls it back.

There is also the lower-level `Begin(AbpUnitOfWorkOptions options, bool requiresNew = false)` on the interface itself.

### The current UOW and `SaveChangesAsync`

UOW is ambient — reach it via `IUnitOfWorkManager.Current` (an `IUnitOfWork`), which is **`null`** when there is no surrounding UOW.

`IUnitOfWork.SaveChangesAsync()` flushes pending changes to the database mid-scope without ending the UOW. If the UOW is transactional, even those saved changes can still be rolled back on a later error. Typical use — get an auto-increment id right after insert:

```csharp
public class CategoryAppService : ApplicationService, ICategoryAppService
{
    private readonly IRepository<Category, int> _categoryRepository;

    public CategoryAppService(IRepository<Category, int> categoryRepository)
        => _categoryRepository = categoryRepository;

    public async Task<int> CreateAsync(string name)
    {
        var category = new Category { Name = name };
        await _categoryRepository.InsertAsync(category);
        await CurrentUnitOfWork.SaveChangesAsync(); // or UnitOfWorkManager.Current.SaveChangesAsync()
        return category.Id;
    }
}
```

`ApplicationService` already exposes `UnitOfWorkManager` and the `CurrentUnitOfWork` shortcut, so you don't inject them there.

- **Don't over-call it.** All changes are saved automatically when the UOW ends without error. Only call `SaveChangesAsync()` (or `InsertAsync(..., autoSave: true)`) when you truly need the flush now.
- With a **`Guid` primary key** you never need to save just to get the id — it's set in-app immediately.

### Nested and reserved UOW

- **Nested / RequiresNew:** call `Begin(requiresNew: true, ...)` inside an existing scope to run an independent inner transaction that commits or rolls back separately from the outer one. Without `requiresNew`, the inner `Begin` just joins the outer UOW.
- **Reserved UOW:** `IUnitOfWorkManager.Reserve(reservationName, requiresNew)` reserves a UOW slot up the stack; later `BeginReserved(reservationName, options)` / `TryBeginReserved(...)` starts the actual UOW under that reservation. `IUnitOfWork.IsReserved` and `ReservationName` reflect this. This is an advanced mechanism used internally (e.g. to make the outermost UOW transactional after inner code has already begun).

### Useful `IUnitOfWork` members

- `CompleteAsync()` / `RollbackAsync()` — commit or roll back a manually-started UOW.
- `OnCompleted(Func<Task>)` — run a callback after the UOW successfully completes (changes are guaranteed saved).
- `Failed` / `Disposed` events — react to failure or disposal.
- `Items` — a `Dictionary<string, object>` to stash arbitrary state scoped to this UOW.
- `Options`, `Outer` — the options it was started with and the enclosing UOW (if nested).

### ASP.NET Core

The UOW system is fully integrated via action/page filters — normally zero config. If you need to widen the scope across other middleware, add `app.UseUnitOfWork();` before `app.UseConfiguredEndpoints();`. `UseUnitOfWork()` is an `IApplicationBuilder` extension in the `Microsoft.AspNetCore.Builder` namespace, shipped by the `Volo.Abp.AspNetCore` package — a plain console/background-worker host that only references `Volo.Abp.Uow` won't have it.

## Validation

- Inside a conventional method (controller action, page handler, app service, repository) `IUnitOfWorkManager.Current` is non-null; outside any scope it is `null`.
- A manually-started `Begin` scope must call `await uow.CompleteAsync()` to commit. Skipping it means an open transaction is never committed (and is disposed on `Dispose()`), so those changes are not persisted — but note this only covers work still buffered in an uncommitted transaction; non-transactional writes that already reached the database are not undone.
- Confirm transaction behavior: only GET requests run without a transaction by default; all other HTTP methods (including QUERY) run transactional (subject to `AbpUnitOfWorkDefaultOptions` and any `NonTransactionalUrls`).
- `[UnitOfWork]` takes effect only as the outermost scope — verify it is not being called inside an existing ambient UOW where it is ignored.

## Common Pitfalls

- **`[UnitOfWork]` ignored inside an ambient UOW** — the attribute only takes effect when it is the outermost scope; an inner call just joins the surrounding UOW.
- **Forgetting `CompleteAsync()` on a manual `Begin`** — `Dispose()` disposes the transaction without committing it (it does not call `RollbackAllAsync`), so an uncommitted transactional UOW discards its changes — even writes already flushed with `SaveChangesAsync` are rolled back when the transaction is disposed (the real commit happens in `CompleteAsync`). What cannot be undone this way is writes made **without** a transaction, which hit the database as they happen.
- **`Begin` without `requiresNew: true` inside an existing scope silently joins the outer UOW** instead of starting an independent transaction.
- **`[UnitOfWork]` not intercepted** — the method must be `async` (`Task`/`Task<T>`), and `virtual` when the service is not injected over an interface.
- **Over-calling `SaveChangesAsync()`** — changes flush automatically when the UOW ends; with a `Guid` PK you never need it just to read the id.
- **`IUnitOfWorkManager.Current` is `null` when no UOW surrounds the call** — guard for it outside conventional scopes.
