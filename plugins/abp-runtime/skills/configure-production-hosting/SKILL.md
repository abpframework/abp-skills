---
name: configure-production-hosting
description: "Release checklist for hosting an ABP app in production behind a reverse proxy or clustered. USE FOR: forwarded headers, shared Data Protection keys, cluster cache/lock, single/multi-instance jobs/workers, SignalR scale-out, shared KeyPrefix. DO NOT USE FOR: the cache/lock APIs (distributed-caching-and-locking); job/worker mechanics (background-jobs-and-events); SignalR hubs (add-signalr-realtime); OpenIddict prod certs (configure-openiddict-authentication)."
license: MIT
---

# Configure Production Hosting (ABP)

A decision checklist for taking an ABP app to production — behind a reverse proxy, or as multiple instances behind a load balancer. This skill routes the *hosting* concerns; the underlying cache/lock/job/worker/SignalR APIs live in sibling skills. Every option below is verified against ABP docs and source.

## When to Use

- Deploying behind a reverse proxy or load balancer (NGINX, IIS, Kubernetes ingress, cloud LB).
- Running **more than one instance** of the app concurrently (a "clustered" deployment — any process: monolith, microservice, console, worker).
- Several apps share one Redis (or one distributed-lock server) and you need to isolate or align their keys.

## When Not to Use

- **How the typed cache / distributed lock APIs work** (`IDistributedCache<T>`, `IAbpDistributedLock`) — **distributed-caching-and-locking**.
- **Defining/enqueuing background jobs, writing workers, publishing events** — **background-jobs-and-events**.
- **Building SignalR hubs / clients** — **add-signalr-realtime**.
- **OpenIddict production signing/encryption certificates** — **configure-openiddict-authentication**.

## The checklist

### 1. Behind a reverse proxy? Configure forwarded headers

Behind a proxy the app sees the proxy's IP/scheme/host, not the client's, so it can generate wrong (e.g. `http://` instead of `https://`) URLs. ABP has **no ABP-specific options class** for this — it relies on ASP.NET Core's built-in `ForwardedHeadersMiddleware`. Configure the standard `ForwardedHeadersOptions` in `ConfigureServices` — include `XForwardedHost` if the proxy rewrites the host, or the external host won't be restored:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.Configure<ForwardedHeadersOptions>(options =>
    {
        options.ForwardedHeaders = ForwardedHeaders.XForwardedFor
            | ForwardedHeaders.XForwardedProto
            | ForwardedHeaders.XForwardedHost;

        // The defaults trust ONLY loopback (KnownIPNetworks/KnownProxies = localhost).
        // Behind nginx / a Kubernetes ingress (non-loopback), the headers are silently
        // ignored until you trust the proxy — add its address/subnet:
        options.KnownProxies.Add(IPAddress.Parse("10.0.0.7"));                    // the proxy's IP, or
        options.KnownIPNetworks.Add(new IPNetwork(IPAddress.Parse("10.0.0.0"), 8)); // its subnet (System.Net.IPNetwork)
        // Clearing both lists ("trust everyone") is a spoofing risk — only do it when the
        // network already guarantees requests can't reach the app except through the proxy.
    });
}
```

Then add the middleware in `OnApplicationInitialization` **before other middleware** — it may run after diagnostics/error handling, but it **must run before `UseHsts`**:

```csharp
public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();
    var env = context.GetEnvironment();

    if (env.IsDevelopment())
    {
        app.UseDeveloperExceptionPage();
        app.UseForwardedHeaders();
    }
    else
    {
        app.UseErrorPage();
        app.UseForwardedHeaders();
        app.UseHsts();
    }
    // ... rest of the pipeline
}
```

`ForwardedHeadersOptions` / `ForwardedHeaders` / `UseForwardedHeaders` are plain ASP.NET Core APIs. See Microsoft's [proxy & load balancer](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/proxy-load-balancer) docs for trusting specific proxies/networks.

### 2. Running more than one instance? Get off in-process state

A single instance can hold state in memory; a cluster cannot — the next request may land on a different instance. Design the app stateless and move shared state out of process:

- **Cache** — the default distributed cache runs *in-memory per instance* and is **not** shared. Add a real provider (Redis via `Volo.Abp.Caching.StackExchangeRedis` + `AbpCachingStackExchangeRedisModule`) for the cluster. Required even if your own code never calls `IDistributedCache` — ABP and pre-built modules use it. (APIs: **distributed-caching-and-locking**.)
- **Distributed lock** — the abstraction runs *in-process by default*, so it is not actually distributed until you register a backing provider. Configure one before relying on cross-instance locking. (APIs: **distributed-caching-and-locking**.)
- **BLOBs** — do **not** use the File System BLOB provider in a cluster (local disk isn't shared). Use the Database provider or a cloud provider — but a BLOB provider is **not** wired by default: install the provider package, add its module dependency, and configure the container. (Setup: **store-blobs**.)
- **Data Protection keys** — see step 3.
- **String encryption** — every instance must share the same `AbpStringEncryptionOptions.DefaultPassPhrase` (namespace `Volo.Abp.Security.Encryption`), otherwise one instance can't decrypt data another wrote. Keep it out of source control (User Secrets / environment variables):

  ```csharp
  Configure<AbpStringEncryptionOptions>(options =>
  {
      options.DefaultPassPhrase = configuration["StringEncryption:DefaultPassPhrase"];
  });
  ```

### 3. Data Protection key persistence across instances

> Not covered in the ABP deployment docs — this is grounded in the ABP startup-template source (`ConfigureDataProtection`) and uses **standard ASP.NET Core Data Protection**, not an ABP-specific API.

Antiforgery tokens, auth cookies, etc. are encrypted with Data Protection keys. In a cluster each instance must read the *same* keyring, or requests handled by another instance fail to decrypt. The ABP templates set the application name and persist keys to Redis outside Development:

```csharp
var dataProtectionBuilder = context.Services.AddDataProtection().SetApplicationName("MyProjectName");
if (!hostingEnvironment.IsDevelopment())
{
    var redis = ConnectionMultiplexer.Connect(configuration["Redis:Configuration"]!);
    dataProtectionBuilder.PersistKeysToStackExchangeRedis(redis, "MyProjectName-Protection-Keys");
}
```

Persisting to a DB (`PersistKeysToDbContext<T>`) is equally valid — the requirement is a *shared, durable* keyring. `SetApplicationName` must be identical across instances that need to share tokens.

### 4. Background jobs & workers — single-instance vs multi-instance

Both run in every instance by default, so in a cluster the same job/work can run multiple times. Pick a strategy:

**Background jobs** — the default manager already uses a distributed lock so jobs execute on only one instance at a time; it works in a cluster **once a distributed-lock provider is configured** (step 2). If you don't want a lock provider, disable execution on all instances but one via `AbpBackgroundJobOptions.IsJobExecutionEnabled` (namespace `Volo.Abp.BackgroundJobs`, default `true`) — other instances can still *enqueue*:

```csharp
Configure<AbpBackgroundJobOptions>(options =>
{
    options.IsJobExecutionEnabled = false; // on all but the one that should run jobs
});
```

Or run a dedicated worker process for jobs. (Job mechanics: **background-jobs-and-events**.)

**Background workers** — no built-in single-instance guarantee. Either take a distributed lock inside the worker so only the holder does the work, or disable workers on all instances but one via `AbpBackgroundWorkerOptions.IsEnabled` (namespace `Volo.Abp.BackgroundWorkers`, default `true`):

```csharp
Configure<AbpBackgroundWorkerOptions>(options =>
{
    options.IsEnabled = false; // on all but the one that should run workers
});
```

Or move all workers into a dedicated process. (Worker mechanics: **background-jobs-and-events**.)

### 5. Using SignalR? Handle scale-out

SignalR pins each client to one server process, so scaling out has two independent needs — **connection affinity** and **cross-server message delivery** — and a Redis backplane only solves the second:

- **Self-hosted cluster:** you need **both** sticky sessions (client affinity) **and** a **Redis backplane** to relay messages between servers. The backplane does **not** remove the sticky-session requirement.
- **Azure SignalR Service:** it owns the client connections, so **no app-server affinity** is required (and no backplane).
- **WebSockets-only + `SkipNegotiation`:** if every client uses WebSockets and skips negotiation, affinity isn't required either.

Standard ASP.NET Core SignalR scale-out, no ABP-specific API. (Building hubs: **add-signalr-realtime**.)

### 6. Sharing one Redis across multiple apps? Set a KeyPrefix

If several *independent* apps share one cache/lock server, isolate them with a prefix (default is empty for both):

```csharp
Configure<AbpDistributedCacheOptions>(options => options.KeyPrefix = "MyCrmApp");   // Volo.Abp.Caching
Configure<AbpDistributedLockOptions>(options => options.KeyPrefix = "MyCrmApp");    // Volo.Abp.DistributedLocking
```

The cache prefix applies only when you use ABP's `IDistributedCache<T>`; with ASP.NET Core's raw `IDistributedCache` you must prefix keys yourself (read the value from `IOptions<AbpDistributedCacheOptions>`).

**Reverse rule for microservices:** all sub-services of *one* system that must stay consistent should share the **same** cache prefix (and normally the same lock prefix, to lock resources globally) — not distinct ones. Some ABP startup templates already set a prefix, so check before adding one.

### 7. Health / readiness endpoints for orchestrators

ABP has **no health-check API** — you use stock ASP.NET Core `AddHealthChecks()` and its `IHealthCheck`. The one ABP-specific wrinkle: register the endpoints through `AbpEndpointRouterOptions.EndpointConfigureActions` (from `Volo.Abp.AspNetCore`) so they compose with ABP's endpoint routing, instead of `app.MapHealthChecks(...)` in a plain `Program.cs`. A custom check is a class implementing `IHealthCheck`, but you must register it explicitly with `.AddCheck<MyCheck>("name", tags: ...)` — implementing the interface (even with `ITransientDependency`) does **not** add it to the health-check registrations by itself. For a DB probe, `AddDbContextCheck<TDbContext>()` (from `Microsoft.Extensions.Diagnostics.HealthChecks.EntityFrameworkCore`).

```csharp
context.Services
    .AddHealthChecks()
    .AddDbContextCheck<MyProjectNameDbContext>("db", tags: new[] { "ready" })
    .AddCheck<MyDependencyHealthCheck>("dependency", tags: new[] { "ready" }); // custom IHealthCheck — must be registered here

context.Services.Configure<AbpEndpointRouterOptions>(options =>
{
    options.EndpointConfigureActions.Add(ctx =>
    {
        // liveness: process is up, run no checks
        ctx.Endpoints.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false });
        // readiness: only checks tagged "ready" (DB, dependencies)
        ctx.Endpoints.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") });
    });
});
```

The turn-key `HealthChecks.UI` dashboard the ABP Studio startup templates scaffold uses third-party Xabaril packages (`AspNetCore.HealthChecks.UI*`), not a framework API — treat that generated code as a starting point, not something ABP ships.

## Validation

- **Forwarded headers:** hit an endpoint through the proxy and confirm generated URLs use the client scheme/host (e.g. `https`) and the real client IP appears in logs. Verify `UseForwardedHeaders` runs before `UseHsts`.
- **Health endpoints:** curl `/health/ready` and `/health/live`; readiness should go Unhealthy (503) when the DB is down while liveness stays Healthy (200).
- **Cluster cache/lock:** confirm the Redis package/module/connection string are wired and a distributed-lock provider is registered — otherwise both fall back to per-instance/in-process and silently don't share.
- **Data Protection:** with two instances up, log in on one and make an authenticated/antiforgery-protected request that gets balanced to the other; it should succeed (shared keyring) rather than 400/re-auth.
- **Jobs/workers:** with multiple instances, confirm a scheduled job/worker fires once, not once per instance.
- **Shared Redis:** inspect keys and confirm they carry the expected prefix.

## Common Pitfalls

- **Inventing an ABP forwarded-headers options class** — there isn't one. Use ASP.NET Core's `ForwardedHeadersOptions` + `UseForwardedHeaders`.
- **`UseForwardedHeaders` after `UseHsts`** — it must come first, or HSTS/redirects run on the wrong scheme.
- **Assuming the default distributed cache is shared** — it is in-memory per instance until you add the Redis provider.
- **Assuming the distributed lock is distributed** — it is in-process until you register a backing provider; jobs/workers relying on it then don't coordinate across instances.
- **No shared Data Protection keyring in a cluster** — auth cookies / antiforgery tokens fail intermittently as the load balancer moves requests between instances.
- **Mismatched `DefaultPassPhrase` across instances** — one instance can't decrypt what another encrypted.
- **File System BLOB provider in a cluster** — local disk isn't shared; use Database or cloud storage.
- **Jobs/workers running on every instance** — duplicate work/emails; use the distributed lock or disable on all but one via `IsJobExecutionEnabled` / `IsEnabled`.
- **Distinct cache prefixes for sub-services that must stay consistent** — microservices of one system should share the same prefix; only isolate *unrelated* apps sharing the server.
