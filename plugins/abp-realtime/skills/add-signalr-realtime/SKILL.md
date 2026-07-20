---
name: add-signalr-realtime
description: >
  Add real-time SignalR features to an ABP app via the Volo.Abp.AspNetCore.SignalR module — creating hubs, wiring conventional hub routes/authorization, reading CurrentUser in a hub, and connecting from a JS or Blazor/.NET client.
  USE FOR: installing the SignalR module, deriving from `AbpHub` (optionally strongly-typed with a client interface), the conventional `/signalr-hubs/...` route and `HubRoute` override, `[Authorize]` + `AbpSignalRUserIdProvider`/`Clients.User`, opting out of auto DI with `[DisableConventionalRegistration]` and auto hub mapping with `[DisableAutoHubMap]` (then configuring manually via `AbpSignalROptions`), and JS/Blazor client connection code.
  DO NOT USE FOR: distributed cache/lock or event-bus-based messaging (use distributed-caching-and-locking / background-jobs-and-events); Dapr pub/sub or inter-service communication (use integrate-dapr-services / design-module-and-service-communication); non-realtime HTTP endpoints (use expose-http-apis).
license: MIT
---

# Add SignalR Real-Time to an ABP App

ABP's `Volo.Abp.AspNetCore.SignalR` module wraps ASP.NET Core SignalR so you don't
have to call `services.AddSignalR()` or map hub endpoints manually — ABP auto-registers
every hub in DI (as transient) and maps its endpoint conventionally.

## When to Use

- Adding server-push / real-time messaging (chat, notifications, live updates) to an ABP app.
- Creating a hub that needs ABP's `CurrentUser` / `CurrentTenant` / localization.
- Securing a hub with `[Authorize]` and targeting connected users by id.
- Connecting to a hub from a JavaScript (MVC/Razor) or Blazor/.NET client.

## When Not to Use

- **Cross-instance/background messaging that isn't client-facing** — use **background-jobs-and-events** (distributed event bus).
- **Dapr pub/sub or inter-microservice messaging** — use **integrate-dapr-services** / **design-module-and-service-communication**.
- **Plain request/response HTTP endpoints** — use **expose-http-apis**.
- Note: hosting/scaling/Redis-backplane/Azure SignalR concerns are standard ASP.NET Core (Microsoft's SignalR docs), not ABP-specific.

## 1. Install the module

Add the package to the web/API layer that hosts your hubs:

```bash
abp add-package Volo.Abp.AspNetCore.SignalR
```

Or add the NuGet package `Volo.Abp.AspNetCore.SignalR` and depend on the module:

```csharp
[DependsOn(
    typeof(AbpAspNetCoreSignalRModule)
)]
public class MyWebModule : AbpModule
{
}
```

You do **not** need `services.AddSignalR()` or a manual `MapHub<T>(...)` — the module
calls `AddSignalR()` and registers each hub's mapping into `AbpEndpointRouterOptions`. It
does **not** call `UseEndpoints` itself, though: your host's request pipeline must include
`app.UseConfiguredEndpoints()` (the startup templates already have it), which is where ABP
runs those hub mappings. If that call is missing, no hub endpoints get mapped.

## 2. Create a hub

Derive from `AbpHub` (or `AbpHub<TClient>` for a strongly-typed client) instead of the
plain `Hub` / `Hub<T>`. `AbpHub` adds useful base members: `CurrentUser`, `CurrentTenant`,
`Logger`, `Clock`, `AuthorizationService`, and localization via `L`.

```csharp
using Microsoft.AspNetCore.Authorization;
using Volo.Abp;
using Volo.Abp.AspNetCore.SignalR;

[Authorize] // require an authenticated user before any hub method runs
public class MessagingHub : AbpHub
{
    // SignalR invokes hub methods by their literal name (it does NOT strip an `Async`
    // suffix), so keep the name the client will call.
    public async Task SendMessage(Guid targetUserId, string message)
    {
        Check.NotNullOrWhiteSpace(message, nameof(message));   // validate untrusted input
        // A real app should also authorize the recipient (contact/room membership, tenant,
        // block lists) — an authenticated user shouldn't be able to message anyone at will.

        var senderUserName = CurrentUser.UserName;      // current (authenticated) user
        Logger.LogInformation("Message from {User}", senderUserName);

        // Deliver only to the target user's connections — don't broadcast arbitrary
        // user input to everyone with Clients.All.
        await Clients.User(targetUserId.ToString())
            .SendAsync("ReceiveMessage", senderUserName, message);
    }
}
```

Strongly-typed client variant:

```csharp
public interface IChatClient
{
    Task ReceiveMessage(string user, string message);
}

[Authorize] // the strongly-typed variant needs the same guard as the plain hub
public class ChatHub : AbpHub<IChatClient>
{
    public Task SendMessage(string message)
    {
        Check.NotNullOrWhiteSpace(message, nameof(message));   // validate untrusted input
        // Clients.All sends to EVERY connection of this hub — it is NOT a room/group. In a
        // shared or multi-tenant host that reaches all users (including other tenants), so
        // only broadcast to everyone when that is genuinely intended; for a real chat room,
        // scope with Clients.Group(...) / Groups.
        return Clients.All.ReceiveMessage(CurrentUser.UserName!, message);
    }
}
```

> A plain `Hub` also works with ABP's auto-registration; `AbpHub` just gives you the
> extra base properties without constructor injection.

## 3. Hub route (URL)

ABP maps the endpoint conventionally. For a hub named `MessagingHub` the route is:

```text
/signalr-hubs/messaging
```

Rule (from `HubRouteAttribute.GetRoutePattern`): prefix `/signalr-hubs/`, then the hub
type name with the `Hub` suffix removed, converted to **kebab-case**.

Override the route with the `HubRoute` attribute:

```csharp
[HubRoute("/my-messaging-hub")]
public class MessagingHub : AbpHub
{
}
```

## 4. Authorization and CurrentUser

Because ABP registers `IUserIdProvider` (`AbpSignalRUserIdProvider`) from `ICurrentUser`,
the hub is integrated with your app's authentication. Protect a hub with the standard
`[Authorize]` attribute:

```csharp
using Microsoft.AspNetCore.Authorization;

[Authorize]
public class MessagingHub : AbpHub
{
    public async Task SendPrivate(string toUserId, string message)
    {
        Check.NotNullOrWhiteSpace(message, nameof(message));
        // A real app should also authorize the recipient (block lists, contact/room
        // membership) — an authenticated user shouldn't be able to message anyone at will.
        // Clients.User(...) works because AbpSignalRUserIdProvider maps to ICurrentUser.Id
        await Clients.User(toUserId).SendAsync("ReceiveMessage", CurrentUser.UserName, message);
    }
}
```

Inside a hub, `CurrentUser` reflects the authenticated connection:

- `CurrentUser.IsAuthenticated`
- `CurrentUser.Id` (a `Guid?`)
- `CurrentUser.UserName`
- `CurrentUser.TenantId` (also available via `CurrentTenant`)

For permission checks you can use the base `AuthorizationService` or an
`[Authorize("MyPermission")]` policy on the hub/method.

## 5. Manual registration / mapping (optional)

Auto DI registration + auto mapping is the default. To opt out of auto DI registration,
put `[DisableConventionalRegistration]` on the hub, then register it yourself:

```csharp
context.Services.AddTransient<MessagingHub>();
```

To keep DI registration but do the endpoint mapping yourself, add
`[DisableAutoHubMap]` and configure via `AbpSignalROptions`:

```csharp
Configure<AbpSignalROptions>(options =>
{
    options.Hubs.Add(
        new HubConfig(
            typeof(MessagingHub),
            "/my-messaging/route",
            hubOptions =>
            {
                hubOptions.LongPolling.PollTimeout = TimeSpan.FromSeconds(30);
            }
        )
    );
});
```

To tweak a hub defined in a depended module you don't own, use `options.Hubs.AddOrUpdate(...)`
with a `config` lambda that sets `config.RoutePattern` and adds to `config.ConfigureActions`.

## 6. Connect from a client

### JavaScript (MVC / Razor Pages)

Add the client package and include the script:

```bash
abp add-package @abp/signalr   # run in the web project root
abp install-libs
```

Include the script in your page/view (requires
`@using Volo.Abp.AspNetCore.Mvc.UI.Packages.SignalR`):

```xml
@section scripts {
    <abp-script type="typeof(SignalRBrowserScriptContributor)" />
}
```

Then use the standard SignalR JS client:

```js
const connection = new signalR.HubConnectionBuilder()
    .withUrl("/signalr-hubs/messaging")
    .build();

connection.on("ReceiveMessage", (user, message) => { /* ... */ });

await connection.start();
await connection.invoke("SendMessage", "3fa85f64-5717-4562-b3fc-2c963f66afa6", "Hello");
```

### Blazor / .NET client

Use the standard `HubConnectionBuilder` from `Microsoft.AspNetCore.SignalR.Client`,
pointing at the conventional route:

```csharp
var connection = new HubConnectionBuilder()
    .WithUrl(NavigationManager.ToAbsoluteUri("/signalr-hubs/messaging"))
    .Build();

connection.On<string, string>("ReceiveMessage", (user, message) => { /* ... */ });

await connection.StartAsync();
```

For an authenticated hub, pass the access token on the client via
`options.AccessTokenProvider` in `WithUrl` per the standard Microsoft SignalR client docs.

### Sending from outside a hub

To send from outside a hub (e.g. an app service), inject
`IHubContext<MessagingHub>` (standard ASP.NET Core) and call
`hubContext.Clients...SendAsync(...)`.

## Validation

- Confirm the hub endpoint is reachable at its conventional route (`/signalr-hubs/<kebab-name-without-Hub-suffix>`, or the `HubRoute` override).
- Verify the host pipeline includes `app.UseConfiguredEndpoints()` — without it no hub endpoints are mapped.
- Start a client (`connection.start()` / `StartAsync()`) and confirm messages round-trip via the registered `on`/`On` handler.
- For an `[Authorize]` hub, confirm `CurrentUser.IsAuthenticated`/`CurrentUser.Id` reflect the connection and `Clients.User(id)` delivers to that user.

## Common Pitfalls

- **Missing `app.UseConfiguredEndpoints()`.** The module registers hub mappings but does not call `UseEndpoints` itself — if that pipeline call is absent, no hub endpoints get mapped (startup templates include it).
- **Manually calling `AddSignalR()` / `MapHub<T>()`.** The module already does both; hubs are auto-registered (transient) and mapped conventionally.
- **Wrong route.** The conventional route strips the `Hub` suffix and kebab-cases the name (`MessagingHub` → `/signalr-hubs/messaging`); override with `[HubRoute]`.
- **Opting out incorrectly.** Use `[DisableConventionalRegistration]` to skip auto DI (then register yourself), or `[DisableAutoHubMap]` + `AbpSignalROptions` to map yourself — they control different things.
- **Treating hosting/scaling as ABP-specific.** Redis backplane, Azure SignalR, and scale-out follow standard ASP.NET Core SignalR guidance, not this skill.
