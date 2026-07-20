---
name: background-jobs-and-events
description: "In-process/cross-service events, entity change reactions, deferred/recurring background work. USE FOR: ILocalEventBus / IDistributedEventBus, EntityCreated/Updated/DeletedEventData, [EventName] ETOs, IBackgroundJobManager jobs, AsyncPeriodicBackgroundWorkerBase workers. DO NOT USE FOR: distributed cache/lock (distributed-caching-and-locking); SignalR push (add-signalr-realtime); microservice message contracts (design-module-and-service-communication)."
license: MIT
---

# Background Jobs & Events (ABP)

Guidance for the ABP event bus (local + distributed), background jobs, and background workers. All APIs below are verified against ABP source. Inject services via constructor; the event bus only subscribes handlers that are already registered in DI, so a handler class must be registered (e.g. by implementing `ITransientDependency` or explicit registration) — implementing the handler interface alone is not enough.

## When to Use

- Decouple code in the same process by publishing/handling local events.
- React to entity create/update/delete performed through a repository.
- Notify other microservices/apps of something that happened (distributed events).
- Queue one-shot work to run later, with automatic retry on failure (background jobs).
- Run recurring/periodic loops (cleanup, polling) as background workers.

## When Not to Use

- **Coordinating a critical section across app instances** or **typed distributed caching** — use the **distributed-caching-and-locking** skill (`IAbpDistributedLock`, `IDistributedCache<T>`).
- **Pushing real-time updates to connected clients** — use the **add-signalr-realtime** skill.
- **Defining the message/contract shape between microservices** at the architecture level — use the **design-module-and-service-communication** skill.

## How it works

### Local event bus (in-process)

`ILocalEventBus` (namespace `Volo.Abp.EventBus.Local`) publishes events within the same process. Publish via the inherited `IEventBus.PublishAsync`:

```csharp
public class MyService : ITransientDependency
{
    private readonly ILocalEventBus _localEventBus;
    public MyService(ILocalEventBus localEventBus) => _localEventBus = localEventBus;

    public async Task DoAsync()
    {
        // onUnitOfWorkComplete defaults to true: published at end of the current UoW
        await _localEventBus.PublishAsync(new StockCountChangedEvent { ProductId = 42, NewCount = 10 });
    }
}
```

Handle by implementing `ILocalEventHandler<TEvent>` (namespace `Volo.Abp.EventBus`). The handler is only subscribed if its class is registered in DI, so add `ITransientDependency` (or register it explicitly):

```csharp
public class StockCountChangedHandler
    : ILocalEventHandler<StockCountChangedEvent>, ITransientDependency
{
    public Task HandleEventAsync(StockCountChangedEvent eventData)
    {
        // ...
        return Task.CompletedTask;
    }
}
```

A single class can implement multiple `ILocalEventHandler<T>` interfaces.

### Entity change events

ABP automatically publishes local events when entities are created/updated/deleted through a repository. Handle them with the generic event data types from `Volo.Abp.Domain.Entities.Events`. The changed entity is on the `.Entity` property:

```csharp
public class ProductCacheInvalidator
    : ILocalEventHandler<EntityCreatedEventData<Product>>,
      ILocalEventHandler<EntityUpdatedEventData<Product>>,
      ILocalEventHandler<EntityDeletedEventData<Product>>,
      ITransientDependency
{
    public Task HandleEventAsync(EntityCreatedEventData<Product> e) => Invalidate(e.Entity);
    public Task HandleEventAsync(EntityUpdatedEventData<Product> e) => Invalidate(e.Entity);
    public Task HandleEventAsync(EntityDeletedEventData<Product> e) => Invalidate(e.Entity);
    private Task Invalidate(Product product) => Task.CompletedTask;
}
```

Hierarchy: `EntityCreatedEventData<T>`, `EntityUpdatedEventData<T>`, `EntityDeletedEventData<T>` all derive from `EntityChangedEventData<T>`, which exposes `TEntity Entity { get; }`. Subscribe to `EntityChangedEventData<T>` to catch all three.

### Distributed event bus (cross-service)

`IDistributedEventBus` (namespace `Volo.Abp.EventBus.Distributed`) publishes across processes/microservices through a provider (RabbitMQ, Kafka, Azure Service Bus, Dapr, Rebus, or the default in-memory one). Note the extra `useOutbox` parameter:

```csharp
Task PublishAsync<TEvent>(TEvent eventData, bool onUnitOfWorkComplete = true, bool useOutbox = true)
    where TEvent : class;
```

Distributed events are transferred as serializable **ETOs** (Event Transfer Objects). Give the ETO a stable, transport-level name with `[EventName]` (namespace `Volo.Abp.EventBus`) so producer and consumer agree regardless of CLR type name:

```csharp
[EventName("MyApp.Stock.Changed")]
public class StockChangedEto
{
    public Guid ProductId { get; set; }
    public int NewCount { get; set; }
}

// publisher
await _distributedEventBus.PublishAsync(new StockChangedEto { ProductId = id, NewCount = count });
```

Handle with `IDistributedEventHandler<TEto>` (namespace `Volo.Abp.EventBus.Distributed`):

```csharp
public class StockChangedHandler
    : IDistributedEventHandler<StockChangedEto>, ITransientDependency
{
    public Task HandleEventAsync(StockChangedEto eventData) => Task.CompletedTask;
}
```

Provider selection is a module + configuration concern (e.g. `AbpEventBusRabbitMqModule`, `AbpEventBusKafkaModule`) plus settings in `appsettings.json`. Keep `useOutbox`/inbox enabled for reliable, transactional delivery when the provider is configured for it.

### Background jobs (deferred, one-shot work)

Use `IBackgroundJobManager` (namespace `Volo.Abp.BackgroundJobs`) to queue work that runs later, retried on failure:

```csharp
Task<string> EnqueueAsync<TArgs>(
    TArgs args,
    BackgroundJobPriority priority = BackgroundJobPriority.Normal,
    TimeSpan? delay = null);
```

```csharp
await _backgroundJobManager.EnqueueAsync(
    new EmailSendingArgs { To = "a@b.com", Subject = "Hi" },
    delay: TimeSpan.FromSeconds(30));
```

`BackgroundJobPriority` values: `Low`, `BelowNormal`, `Normal` (default), `AboveNormal`, `High`.

Define the job by deriving from `AsyncBackgroundJob<TArgs>` (implements `IAsyncBackgroundJob<TArgs>`) and overriding `ExecuteAsync`. The args type is how the job is looked up.

```csharp
public class EmailSendingJob : AsyncBackgroundJob<EmailSendingArgs>, ITransientDependency
{
    public override async Task ExecuteAsync(EmailSendingArgs args)
    {
        // send email; a Logger property is available from the base class
    }
}
```

For synchronous jobs, derive from `BackgroundJob<TArgs>` (`IBackgroundJob<TArgs>`) and override `void Execute(TArgs args)`. Prefer the async version. The startup template ships the Background Jobs module, which **persists jobs in the database by default** (so they survive restarts and are retried); the framework only falls back to an in-memory store when no persistent job-store module is installed. Hangfire, Quartz, and RabbitMQ are alternative providers you can swap in — not a requirement for production.

### Dynamic background jobs (enqueue by name)

When the job type isn't known at compile time (plugin systems, dynamic workflows), use `IDynamicBackgroundJobManager` (namespace `Volo.Abp.BackgroundJobs`) to enqueue **by job name**:

```csharp
// enqueue a typed job (named with [BackgroundJobName("emails")]) by its name
await _dynamicJobManager.EnqueueAsync("emails", new { To = "user@example.com", Subject = "Hi" });

// or register a handler at runtime and enqueue against it
_dynamicJobManager.RegisterHandler("ProcessOrder", async (context, ct) => { /* ... */ });
await _dynamicJobManager.EnqueueAsync("ProcessOrder", new { OrderId = orderId });
```

`EnqueueAsync(name, args)` looks up the job by `[BackgroundJobName]` (or a runtime-registered handler), deserializes the args, and runs through the same persistent pipeline as typed jobs. Use typed `IBackgroundJobManager` when the job type is known; reach for the dynamic manager only when it genuinely isn't (the args are loosely typed, so you lose compile-time checking).

### Background workers (recurring work)

For periodic loops, derive from `AsyncPeriodicBackgroundWorkerBase` (namespace `Volo.Abp.BackgroundWorkers`). Its constructor takes `AbpAsyncTimer timer` and `IServiceScopeFactory serviceScopeFactory`; set `timer.Period` (milliseconds) and override `DoWorkAsync`. Each run gets a fresh DI scope via `workerContext.ServiceProvider` — resolve scoped services from there, not the constructor:

```csharp
public class CleanupWorker : AsyncPeriodicBackgroundWorkerBase
{
    public CleanupWorker(AbpAsyncTimer timer, IServiceScopeFactory scopeFactory)
        : base(timer, scopeFactory)
    {
        Timer.Period = 60_000; // every 60s
    }

    protected override async Task DoWorkAsync(PeriodicBackgroundWorkerContext workerContext)
    {
        var repo = workerContext.ServiceProvider
            .GetRequiredService<IRepository<StaleRecord, Guid>>();
        // ... do periodic work
    }
}
```

`AsyncPeriodicBackgroundWorkerBase` also exposes a `CronExpression` property, but the **default in-memory worker only schedules by `Period`** — its `AbpAsyncTimer` ignores `CronExpression`. Cron scheduling is honored only when you use a Hangfire, Quartz, or TickerQ background-worker provider.

Register the worker in your module's `OnApplicationInitializationAsync` with the extension `AddBackgroundWorkerAsync<TWorker>` on `ApplicationInitializationContext`:

```csharp
public override async Task OnApplicationInitializationAsync(ApplicationInitializationContext context)
{
    await context.AddBackgroundWorkerAsync<CleanupWorker>();
}
```

To add a worker at runtime, resolve `IBackgroundWorkerManager` and call `AddAsync(IBackgroundWorker worker)`. Custom workers can also derive from `BackgroundWorkerBase` (which implements `IBackgroundWorker`) for full control.

### Choosing the right tool

- **Local event bus** — decouple code in the same process/app; entity change reactions.
- **Distributed event bus** — notify other microservices/apps; use `[EventName]` + ETO.
- **Background job** — run one-shot work later, with retries (emails, reports).
- **Background worker** — run recurring/periodic work (cleanup, polling).

## Provider integrations (mainstream)

Each provider needs its `[DependsOn]` module. The **configuration shape differs per provider** — some use `Configure<...Options>`, some `PreConfigure<...>`, and some also need an initialization-phase call (see the note below the examples). `appsettings.json` config works too, and values set in code take precedence over it.

### Background jobs

**Hangfire** — depend on `AbpBackgroundJobsHangfireModule` and wire a Hangfire storage/server in `ConfigureServices` (Hangfire has no ABP options class; you configure Hangfire itself):

```csharp
[DependsOn(typeof(AbpBackgroundJobsHangfireModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        var configuration = context.Services.GetConfiguration();
        context.Services.AddHangfire(config =>
            config.UseSqlServerStorage(configuration.GetConnectionString("Default")));
    }
}
```

**RabbitMQ** — depend on `AbpBackgroundJobsRabbitMqModule`; connections come from the `RabbitMQ:Connections` config (default = localhost), and `AbpRabbitMqBackgroundJobOptions` customizes queue names/connections per job:

```csharp
Configure<AbpRabbitMqBackgroundJobOptions>(options =>
{
    options.DefaultQueueNamePrefix = "my_app_jobs.";
    options.JobQueues[typeof(EmailSendingArgs)] = new JobQueueConfiguration(
        typeof(EmailSendingArgs),
        queueName: "my_app_jobs.emails",
        delayedQueueName: "my_app_jobs.emails.delayed", // required ctor arg
        connectionName: "Default");
});
```

### Background workers

Swap the default in-memory worker timer for a provider that honors `CronExpression` — but the two mainstream providers are **not** both zero-config:

- **Hangfire** (`AbpBackgroundWorkersHangfireModule`) needs a **Hangfire storage/server configured**, exactly like the Hangfire *job* provider above (`AddHangfire(config => config.UseSqlServerStorage(...))`). The module adapts your workers but does **not** pick or configure storage — without it Hangfire fails to start.
- **Quartz** (`AbpBackgroundWorkersQuartzModule`) runs on Quartz's default in-memory (RAM) store with no options; for production, configure a persistent Quartz store.

```csharp
[DependsOn(typeof(AbpBackgroundWorkersQuartzModule))] // Quartz: in-memory store by default
// or AbpBackgroundWorkersHangfireModule — then also configure Hangfire storage (see the Hangfire job example above)
public class MyModule : AbpModule { }
```

Your existing `AsyncPeriodicBackgroundWorkerBase` workers, registered the same way with `context.AddBackgroundWorkerAsync<TWorker>()`, are then dispatched by the chosen provider (Hangfire adapts them via `HangfirePeriodicBackgroundWorkerAdapter`). This is what makes `CronExpression` honored on Quartz/Hangfire/TickerQ, unlike the default in-memory timer.

### Distributed event bus

**RabbitMQ** — depend on `AbpEventBusRabbitMqModule`; `AbpRabbitMqEventBusOptions` sets `ConnectionName`, `ClientName` (the queue name for this app), and `ExchangeName`:

```csharp
[DependsOn(typeof(AbpEventBusRabbitMqModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpRabbitMqEventBusOptions>(options =>
        {
            options.ClientName = "MyApp";
            options.ExchangeName = "MyMessages";
        });
    }
}
```

**Kafka** — depend on `AbpEventBusKafkaModule`; `AbpKafkaEventBusOptions` sets `ConnectionName`, `GroupId` (consumer group), and `TopicName`:

```csharp
[DependsOn(typeof(AbpEventBusKafkaModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpKafkaEventBusOptions>(options =>
        {
            options.GroupId = "MyGroupId";
            options.TopicName = "MyTopicName";
        });
    }
}
```

The other providers (Quartz/TickerQ for jobs, Azure Service Bus/Rebus for the event bus) each add their `[DependsOn]` module, but the configuration shape is **not** uniform — check each provider's doc:

- **Rebus** configures in `PreConfigureServices` via `PreConfigure<AbpRebusEventBusOptions>(...)`, not `Configure`.
- **TickerQ** also needs an initialization-phase call — `context.GetHost().UseAbpTickerQ()` in `OnApplicationInitialization` (the `UseAbpTickerQ` extension is on `IHost`, not the context), not just options.
- **Quartz** uses two options at different phases: `PreConfigure<AbpQuartzOptions>(...)` for the scheduler plus `Configure<AbpBackgroundJobQuartzOptions>(...)` for the job integration.

## Validation

- Build the module. Workers are resolved and started at initialization; event handlers are resolved from DI each time the event fires, and jobs are resolved from DI at execution time.
- For a local/distributed handler, confirm it is registered in DI (implements `ITransientDependency` or is registered explicitly) — an unregistered handler is silently never invoked.
- For a background worker, confirm registration via `context.AddBackgroundWorkerAsync<TWorker>()` and observe `DoWorkAsync` firing on the configured `Timer.Period` (or the `CronExpression`, only if you run a Hangfire/Quartz/TickerQ provider).
- For a background job, confirm `ExecuteAsync` runs after the configured `delay` (with a persistent provider wired in for anything beyond dev).

## Common Pitfalls

- **Implementing the handler interface is not enough** — the event bus only subscribes handlers already registered in DI. Add `ITransientDependency` or register the class explicitly, or it never fires.
- **Resolving scoped services from a background worker's constructor** — each `DoWorkAsync` run gets a fresh scope; resolve scoped services from `workerContext.ServiceProvider`, not the constructor.
- **Relying on CLR type names for distributed events** — producer and consumer must agree on a stable `[EventName]` on the ETO, or delivery breaks when type names differ across services.
- **Running background jobs without a persistent store** — the in-memory store is only the framework *fallback* used when neither the Background Jobs module nor a custom `IBackgroundJobStore` is installed. The startup template already installs the module with a database store (per your ORM), which **is** production-usable; Hangfire/Quartz/RabbitMQ are optional alternative providers, not a requirement. In a **cluster**, still configure a distributed lock so jobs execute on one instance.
- **Assuming distributed delivery is reliable by default** — keep `useOutbox`/inbox enabled (with a provider configured for it) for transactional delivery.
