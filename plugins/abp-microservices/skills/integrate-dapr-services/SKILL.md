---
name: integrate-dapr-services
description: >
  Run ABP's own abstractions (client proxies, distributed event bus, distributed lock) over a Dapr sidecar with little or no code change.
  USE FOR: adding the Volo.Abp.Dapr modules, invoking services through Dapr service invocation, backing IDistributedEventBus with Dapr pub/sub, using Dapr for distributed locking, securing receive endpoints with the App API token; also when you see Dapr app-ids, sidecars, or [Topic] attributes in an ABP project.
  DO NOT USE FOR: deciding sync-vs-async or the outbox/inbox and idempotency design itself (use design-module-and-service-communication); plain HTTP client proxies without Dapr (use consume-remote-services); non-Dapr distributed locking/caching providers (use the distributed-caching-and-locking skill).
license: MIT
---

# ABP Dapr Integration

[Dapr](https://dapr.io/) decouples common microservice concerns (service invocation, pub/sub, locking) into a sidecar runtime. ABP ships integration packages so its own abstractions (client proxies, `IDistributedEventBus`, `IAbpDistributedLock`) run *over* Dapr with little or no code change. ABP and Dapr are complementary — ABP gives the opinionated architecture, Dapr the runtime plumbing.

## When to Use

- Adding the `Volo.Abp.Dapr` modules to an ABP solution.
- Routing ABP client proxies through Dapr service invocation.
- Backing the distributed event bus with Dapr pub/sub (publish and/or receive).
- Using Dapr's building block for `IAbpDistributedLock`.
- Securing Dapr receive endpoints with the App API token.
- Working in a project that already uses Dapr app-ids, sidecars, or `[Topic]` attributes.

## When Not to Use

- **Deciding whether to communicate sync vs async**, or designing the outbox/inbox and idempotency — use the **design-module-and-service-communication** skill (this skill is the Dapr *transport*, not the design).
- **Plain HTTP client proxies without Dapr** — use the **consume-remote-services** skill.
- **Non-Dapr distributed locking / caching providers** — use the **distributed-caching-and-locking** skill.

## How it works

### Packages

Add only what you need; each depends on the core `Volo.Abp.Dapr`:

- **`Volo.Abp.Dapr`** — core package (`AbpDaprModule`). Provides `AbpDaprOptions` and `IAbpDaprClientFactory`. Everything else references it.
- **`Volo.Abp.Http.Client.Dapr`** (`AbpHttpClientDaprModule`) — routes ABP's dynamic/static C# client proxies through Dapr service invocation.
- **`Volo.Abp.EventBus.Dapr`** (`AbpEventBusDaprModule`) — distributed event bus over Dapr pub/sub. **Publish only** (can send, can't receive).
- **`Volo.Abp.AspNetCore.Mvc.Dapr.EventBus`** (`AbpAspNetCoreMvcDaprEventBusModule`) — adds the subscription endpoints so an ASP.NET Core app can also **receive** events. Already references `Volo.Abp.EventBus.Dapr`, so install this one to send *and* receive.
- **`Volo.Abp.DistributedLocking.Dapr`** (`AbpDistributedLockingDaprModule`) — backs `IAbpDistributedLock` with Dapr's lock building block.

Install a package with `abp add-package Volo.Abp.Dapr` (etc.), or manually add the NuGet reference plus `[DependsOn(typeof(AbpDaprModule))]` on your module class.

### Core options and client factory

`AbpDaprModule` binds the `Dapr` section of configuration into `AbpDaprOptions`. All settings are optional — you usually configure nothing:

```csharp
Configure<AbpDaprOptions>(options =>
{
    // HttpEndpoint, GrpcEndpoint, DaprApiToken, AppApiToken
});
```

```json
"Dapr": { "HttpEndpoint": "http://localhost:3500/" }
```

`DaprApiToken` defaults from the `DAPR_API_TOKEN` env var and `AppApiToken` from `APP_API_TOKEN` — both set by Dapr at runtime, so they're normally auto-filled.

Use `IAbpDaprClientFactory` to build `DaprClient` / `HttpClient` objects that already honor these options:

```csharp
public class MyService : ITransientDependency
{
    private readonly IAbpDaprClientFactory _daprClientFactory;
    public MyService(IAbpDaprClientFactory daprClientFactory)
        => _daprClientFactory = daprClientFactory;

    public async Task DoItAsync()
    {
        DaprClient daprClient = await _daprClientFactory.CreateAsync();
        HttpClient httpClient = await _daprClientFactory.CreateHttpClientAsync("target-app-id");
    }
}
```

### Service invocation (client proxies over Dapr)

With `Volo.Abp.Http.Client.Dapr` installed, point ABP's remote service base URL at the target **Dapr app-id** instead of a host:

```json
{
  "RemoteServices": {
    "Default": { "BaseUrl": "http://dapr-httpapi/" }
  }
}
```

Here `dapr-httpapi` is the server app's Dapr application id. The remote service name (`Default`) must match the name used in `AddHttpClientProxies` / `AddStaticHttpClientProxies`. After that, your existing client-proxy calls automatically go through Dapr's service invocation building block — no call-site changes.

### Distributed event bus over Dapr pub/sub

Once the pub/sub packages are installed, use the event bus exactly as documented for [distributed events](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/event-bus/distributed/index.md) — publish with `IDistributedEventBus.PublishAsync`, subscribe by implementing `IDistributedEventHandler<TEvent>`. ABP auto-registers your handlers with Dapr; no application code change to switch to Dapr as the provider.

Configure the pub/sub component name (defaults to `pubsub`):

```csharp
Configure<AbpDaprEventBusOptions>(options =>
{
    options.PubSubName = "pubsub";
});
```

ABP exposes two endpoints Dapr uses:

- `dapr/subscribe` — Dapr fetches the subscription list here (ABP fills it from your handlers and any `[Topic]` controller actions).
- `api/abp/dapr/event` — the unified receive endpoint; ABP dispatches to the right handler by topic.

> ABP calls `MapSubscribeHandler` internally — don't call it yourself. Add `app.UseCloudEvents()` if you want CloudEvents support.

Two Dapr-specific caveats:

- **Dynamic (string-based) events are not supported** on the Dapr provider — Dapr needs topic subscriptions declared at startup and can't add them at runtime. Calling `Subscribe(string, ...)` on it throws `AbpException`.
- Publishing directly via `DaprClient.PublishEventAsync` bypasses ABP features like the **outbox/inbox** pattern; prefer `IDistributedEventBus` to keep them.

### Distributed locking with Dapr

`Volo.Abp.DistributedLocking.Dapr` makes `IAbpDistributedLock` use Dapr's lock building block. Configure the store:

```csharp
Configure<AbpDistributedLockDaprOptions>(options =>
{
    options.StoreName = "mystore"; // required
    // Owner (optional), DefaultExpirationTimeout (optional, default 2 min)
});
```

Usage is the standard ABP lock API:

```csharp
await using (var handle = await _distributedLock.TryAcquireAsync("MyLockName"))
{
    if (handle != null)
    {
        // exclusive access to the shared resource
    }
}
```

Two differences from ABP's default lock providers:

- `timeout` on `TryAcquireAsync` is ignored — Dapr doesn't wait to acquire.
- The lock auto-expires after `DefaultExpirationTimeout` even if not released; there's no per-call expiration parameter.

> ABP's docs note Dapr's distributed-lock building block is at Alpha stage and its API may change — for production locking, ABP still recommends the DistributedLock-library providers over Dapr.

### Security (App API token)

When traffic flows through Dapr, protect your receive endpoints with the App API token. In an event-handling action, validate it:

```csharp
[HttpPost("/stock-changed")]
[Topic("pubsub", "StockChanged")]
public async Task<IActionResult> OnStockChangedAsync([FromBody] StockCountChangedEto model)
{
    HttpContext.ValidateDaprAppApiToken(); // throws if the token is missing/wrong
    return Ok();
}
```

`ValidateDaprAppApiToken()` checks the `dapr-api-token` header (no-op if you haven't configured App API token). Outside controllers, inject `IDaprAppApiTokenValidator`. Enabling App API token validation is strongly recommended so arbitrary callers can't hit your subscription endpoints.

## Validation

- Confirm the Dapr sidecar is running and the app-id used in `RemoteServices.BaseUrl` matches the target's Dapr application id; a proxy call then reaches the target via service invocation with no call-site change.
- For pub/sub, confirm Dapr can fetch the subscription list from `dapr/subscribe` and that published events arrive at `api/abp/dapr/event` and dispatch to the right handler.
- For locking, acquire `TryAcquireAsync("MyLockName")` against the configured `StoreName` and verify mutual exclusion.
- Hit a receive endpoint without a valid `dapr-api-token` header and confirm `ValidateDaprAppApiToken()` rejects it (once App API token is configured).

## Common Pitfalls

- `Volo.Abp.EventBus.Dapr` is **publish-only**; to also receive events install `Volo.Abp.AspNetCore.Mvc.Dapr.EventBus` (it references the event bus package).
- Don't call `MapSubscribeHandler` yourself — ABP does it internally; add `app.UseCloudEvents()` only if you want CloudEvents.
- **Dynamic (string-based) events are not supported** over Dapr — `Subscribe(string, ...)` throws `AbpException`, because Dapr needs subscriptions declared at startup.
- Publishing directly via `DaprClient.PublishEventAsync` bypasses ABP's outbox/inbox — go through `IDistributedEventBus` to keep them.
- Dapr's distributed lock ignores the `TryAcquireAsync` `timeout` (no wait) and auto-expires after `DefaultExpirationTimeout` with no per-call override; its building block is Alpha — prefer the DistributedLock-library providers for production.
- Enable App API token validation so arbitrary callers can't hit your subscription endpoints; `ValidateDaprAppApiToken()` is a no-op until the token is configured.

## See also

- ABP Dapr integration: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/dapr/index.md`
- Distributed Event Bus: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/event-bus/distributed/index.md`
- Distributed Locking: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/distributed-locking.md`
