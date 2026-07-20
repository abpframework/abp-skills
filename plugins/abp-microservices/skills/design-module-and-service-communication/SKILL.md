---
name: design-module-and-service-communication
description: >
  Decide how two ABP modules or microservices communicate — synchronous integration services vs asynchronous distributed events — and make events reliable and idempotent.
  USE FOR: choosing sync (integration services — in-process DI in a monolith, HTTP client proxy across microservices) vs async (distributed event bus), publishing/subscribing distributed events (ETOs, [EventName], IDistributedEventHandler), enabling the transactional outbox/inbox, keeping handlers idempotent, cross-module/service query and reporting boundaries, sharing contracts without leaking a module's or service's internals.
  DO NOT USE FOR: the mechanics of exposing an integration service as a controller (use expose-http-apis); the mechanics of calling a remote service via client proxies (use consume-remote-services); running that communication over a Dapr sidecar / pub-sub (use integrate-dapr-services); in-process background jobs and local events (use the background-jobs-and-events skill).
license: MIT
---

# Designing ABP Module & Service Communication

Two building blocks cover almost all communication across a boundary in ABP — whether the boundary is between **modules in a modular monolith** (one process) or between **microservices** (separate processes). Pick per interaction, not per system — most solutions use both. Designing for module boundaries first is what lets a modular monolith later split into microservices with little communication rework: the distributed event bus and integration services run in-process today and swap to a broker/remote transport with little application-code change — though the split still adds remote auth, network-failure/timeout handling, and cross-service consistency to design for.

## When to Use

- Deciding whether an interaction should be synchronous (needs an immediate answer) or asynchronous (fire-and-forget notification), between modules or between microservices.
- Publishing/subscribing to distributed events across a module or service boundary.
- Making cross-boundary events reliable and transactional with the outbox/inbox.
- Keeping event handlers idempotent against duplicate delivery.
- Sharing contracts (ETOs, integration DTOs) across a boundary without leaking domain entities.
- Designing a cross-module/service query or report without coupling to another module's internals.

## When Not to Use

- **The mechanics of exposing an `[IntegrationService]` as an HTTP controller** — use the **expose-http-apis** skill.
- **The mechanics of calling a remote service through client proxies** — use the **consume-remote-services** skill.
- **Running this communication over a Dapr sidecar / pub-sub** — use the **integrate-dapr-services** skill.
- **In-process background jobs and local (single-service) events** — use the **background-jobs-and-events** skill.

## How it works

### Synchronous vs. Asynchronous — which to use

**Synchronous (Integration Services)** — use when the caller needs an immediate answer (a query, or a command whose result it must have before continuing). The caller invokes the callee's integration service and waits. How that call travels depends on topology: an **in-process** call between modules of a monolith, or a **remote HTTP call** between microservices (see below) — the same interface, different transport.

**Asynchronous (Distributed Event Bus)** — use when a service just needs to *announce* that something happened and doesn't care who reacts or when. Publisher and subscribers are decoupled; this is the recommended default for propagating state changes between services.

> Rule of thumb: read/command-with-result → integration service; "X happened" notification → distributed event. Prefer async to keep services loosely coupled.

### Synchronous: Integration Services

An *integration service* is an application service (or MVC controller) meant for service-to-service calls, not for UI/3rd-party clients. Mark it with `[IntegrationService]`:

```csharp
[IntegrationService]
public interface IProductIntegrationService : IApplicationService
{
    Task<ProductDto> GetAsync(Guid id);
}

[IntegrationService] // not required again if already on the interface
public class ProductIntegrationService : ApplicationService, IProductIntegrationService
{
    public Task<ProductDto> GetAsync(Guid id)
    {
        // ... load and map the product ...
        return Task.FromResult(new ProductDto());
    }
}
```

By convention ABP does **not expose** an integration service over HTTP by default (and disables its **audit logging**). Whether you expose it depends on whether the caller runs in the same process:

**Modular monolith — modules in one process.** The caller module references the owner module's **Application.Contracts** package (which holds `IProductIntegrationService` + its DTOs), then injects and calls the interface **directly through DI** — an ordinary in-process method call. Do **not** set `ExposeIntegrationServices`; there is no HTTP, no `/integration-api`, no client proxy. This is the default for a monolith. Consume it from the **Application layer** (an application/integration service), as the ABP tutorials do:

```csharp
// consuming module — inject in the Application layer, in-process, no HTTP
public class OrderAppService : ApplicationService
{
    private readonly IProductIntegrationService _products;
    public OrderAppService(IProductIntegrationService products) => _products = products;

    public Task<ProductDto> GetProductAsync(Guid id) => _products.GetAsync(id);
}
```

A module's **Domain** layer must **not** inject another module's integration service: that interface lives in `Application.Contracts`, and ABP's layering forbids a `Domain` project from depending on any `Application.Contracts` (Domain depends only on Domain.Shared). If a domain rule needs data from another module, fetch it in the Application layer and pass the values into the domain object/service.

**Microservice — separate processes.** The owner service must opt in to expose the integration service over HTTP (served under `/integration-api` instead of `/api`, which the gateway should block from outside your private network):

```csharp
Configure<AbpAspNetCoreMvcOptions>(options =>
{
    options.ExposeIntegrationServices = true;
});
```

The consuming service then calls it through ABP's dynamic or static C# **client proxies** — same interface, remote call. Keep integration-service contracts small and stable; they are an API surface between services.

Designing for the monolith case first (Contracts + direct DI) is what lets a module later split into a microservice without rewriting the caller's business logic: the owner flips `ExposeIntegrationServices` on, and the consumer swaps direct DI for a client proxy of the *same* interface. The split still adds remote authentication, network-failure/timeout handling, and cross-service data consistency to design for — the stable contract just keeps it from being a business-logic rewrite.

### Asynchronous: Distributed Event Bus

`IDistributedEventBus` publishes events across service boundaries. The default `LocalDistributedEventBus` runs in-process, so you can write distributed-ready code in a monolith and later plug in RabbitMQ / Kafka / Azure Service Bus / Rebus with no code change.

Publish an Event Transfer Object (ETO — a plain, serializable class; `Eto` suffix by convention):

```csharp
[EventName("MyApp.Product.StockChanged")]
public class StockCountChangedEto
{
    public Guid ProductId { get; set; }
    public int NewCount { get; set; }
}

// in a service
await _distributedEventBus.PublishAsync(
    new StockCountChangedEto { ProductId = id, NewCount = newCount });
```

Subscribe by implementing `IDistributedEventHandler<TEvent>` (auto-discovered when registered in DI):

```csharp
public class StockChangedHandler
    : IDistributedEventHandler<StockCountChangedEto>, ITransientDependency
{
    public async Task HandleEventAsync(StockCountChangedEto eventData)
    {
        // react to the change
    }
}
```

Give the event a stable `[EventName]` — it's the wire contract that matches publisher and subscriber across services.

### Reliable events: the Outbox / Inbox pattern

With a real broker, publisher and handler run in different processes, so you can't rely on a shared transaction. The transactional **outbox** saves outgoing events into your DB in the *same* transaction as your data change, then a background worker ships them to the broker with retries — no lost events if the broker is briefly down. The **inbox** persists incoming events first, then processes each one inside a transaction and marks it `Processed` (it does *not* delete the record in that transaction — a background cleanup removes processed records later, after a retention window). Persisting + marking events is what gives you de-duplication.

Prerequisites: configure the [distributed lock system](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/distributed-locking.md) (used to serialize box processing across instances) and use EF Core or MongoDB.

Enable outbox on an EF Core `DbContext`:

```csharp
public class MyDbContext : AbpDbContext<MyDbContext>, IHasEventOutbox, IHasEventInbox
{
    public DbSet<OutgoingEventRecord> OutgoingEvents { get; set; }
    public DbSet<IncomingEventRecord> IncomingEvents { get; set; }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);
        builder.ConfigureEventOutbox();
        builder.ConfigureEventInbox();
    }
}
```

Add a migration for the new tables, then register the boxes:

```csharp
Configure<AbpDistributedEventBusOptions>(options =>
{
    options.Outboxes.Configure(config => config.UseDbContext<MyDbContext>());
    options.Inboxes.Configure(config => config.UseDbContext<MyDbContext>());
});
```

(MongoDB is analogous: `IMongoCollection<OutgoingEventRecord>` / `IncomingEventRecord` + `modelBuilder.ConfigureEventOutbox()/ConfigureEventInbox()`.)

Outbox/inbox can be enabled independently. To bypass the outbox for a specific publish, pass `useOutbox: false` to `PublishAsync`. Fine-tune polling, cleanup and failure handling via `AbpEventBusBoxesOptions` (e.g. `PeriodTimeSpan`, `InboxProcessorFailurePolicy` = `Retry` / `RetryLater` / `Discard`).

### Idempotency

The inbox de-duplicates the *transport*, but design handlers to be idempotent anyway — a broker may still deliver twice, and processing may retry after a partial failure. Practical guidance:

- Make the effect safe to apply more than once (upsert / "set to state X" rather than "increment"), keyed by the entity id in the event.
- For syncing a remote entity's copy locally, use ABP's `EntitySynchronizer<TEntity, TKey, TSourceEntityEto>` base class. It subscribes to create/update/delete events; combined with entity versioning (`IHasEntityVersion`), the **create/update** path skips an incoming event whose version is older than the local copy, giving a mostly idempotent sync. Two caveats: the version check accepts the *same* version too (it uses `>=`, so a re-delivered same-version update isn't rejected), and the **delete** path has no version check at all — a delete event is applied whenever a matching local entity exists, regardless of ordering. So don't rely on it to fully order or drop stale deletes; keep your own handlers idempotent as well.

### Sharing contracts safely

Only share what is genuinely a contract — ETOs and integration-service interfaces/DTOs — never a service's domain entities or internal implementation.

- Put ETOs / integration DTOs in a small **Contracts** package (e.g. the service's `.Application.Contracts`) that other services reference. Keep it minimal and versioned.
- To avoid a shared-package dependency entirely, **copy** the ETO into the consuming service. This works precisely because `[EventName("...")]` is the real contract — the same event name maps the two copies across services. Match the event name exactly.
- Consumers should model only the subset of fields they need (e.g. `OrderProduct` copies a few `Product` fields), not mirror the source entity. This keeps service boundaries strong.

### Cross-module / cross-service queries & reporting

A read that spans two boundaries is the same design problem as a write. Default to the same rule: a module/service references only another's **Contracts** (its integration service or ETOs), never its entities or `DbContext`. Query the owner through its integration service, or keep a local read model synced from its events and join in memory.

When a report genuinely needs to join large data sets across boundaries and per-call integration queries are too costly, put that join in an **explicit reporting/aggregation module** that is *allowed* to read from multiple sources — and accept that this module is deliberately coupled to those databases. Keep that coupling in one clearly named place instead of letting arbitrary modules reach into each other. In a modular monolith the sources may be separate schemas in one physical database; when splitting into microservices, the reporting module becomes a service fed by events or backed by a dedicated reporting store.

## Validation

- For sync calls in a **monolith**: confirm the caller injects the integration-service interface from the owner module's Contracts and the call resolves in-process — `ExposeIntegrationServices` stays off and nothing hits `/integration-api`. For sync calls across **microservices**: with `ExposeIntegrationServices = true`, confirm the service is reachable under `/integration-api` and the consuming service's client proxy gets a response.
- For async events: publish an ETO and confirm the subscriber's `IDistributedEventHandler<TEvent>` fires. Matching is by event name — without `[EventName]` ABP falls back to `eventType.FullName`, so this works only if both sides resolve to the same name (same CLR type, or the same explicit `[EventName]` on each copy).
- For outbox/inbox (EF Core): after adding the migration, confirm the outgoing/incoming event tables exist; publish an event and observe the outgoing record persisted in the same transaction and the incoming record marked `Processed` after handling.
- For outbox/inbox (MongoDB): there's no migration or table — confirm `ConfigureEventOutbox`/`ConfigureEventInbox` are wired and check the outgoing/incoming `IMongoCollection` documents instead.

## Common Pitfalls

- Integration services are **not exposed** and have **audit logging disabled** by default — opt in with `ExposeIntegrationServices` when a remote service must reach them.
- Prefer async distributed events for state-change propagation; overusing sync integration calls couples services tightly.
- Event name is the wire contract — without `[EventName]` ABP uses `eventType.FullName`, so publisher and subscriber match only when both resolve to the same name. Set an explicit `[EventName]` to keep a stable wire name and to let you *copy* an ETO into a different CLR type instead of sharing a package; a mismatch between the two sides silently breaks matching.
- Outbox/inbox require the **distributed lock system** configured. On **EF Core** the box lives in tables — forgetting the migration breaks processing; on **MongoDB** there are no tables/migration, you wire `ConfigureEventOutbox`/`ConfigureEventInbox` and the records live in `IMongoCollection`s.
- The inbox de-duplicates transport only — still make handlers idempotent (upsert / set-state, not increment).
- `EntitySynchronizer` version check uses `>=` (a re-delivered same-version update isn't rejected), and its **delete** path has no version check at all — don't rely on it to order or drop stale deletes.
- Never share domain entities or internals across services — only ETOs and integration DTOs, in a minimal Contracts package.

## See also

- Distributed Event Bus: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/event-bus/distributed/index.md`
- Integration Services: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/api-development/integration-services.md`
- Microservices overview: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/architecture/microservices/index.md`
