---
name: consume-remote-services
description: >
  Call a remote ABP HTTP API from C# through generated client proxies instead of raw HttpClient.
  USE FOR: setting up dynamic (runtime) or static (build-time) client proxies, configuring AbpRemoteServiceOptions (BaseUrl / named endpoints), wiring tiered / microservice calls, authenticating proxy calls (forward the current user token with AbpHttpClientIdentityModelWebModule, or client credentials with AbpHttpClientIdentityModelModule + IdentityClients), adding Polly retry to proxy clients.
  DO NOT USE FOR: exposing your own services as HTTP APIs or auto controllers (use expose-http-apis); choosing sync HTTP vs async events between services or the outbox/inbox (use design-module-and-service-communication); routing proxies through Dapr service invocation (use integrate-dapr-services).
license: MIT
---

# Consume ABP Remote Services with C# Client Proxies

ABP generates client proxies so you call a remote HTTP API through its C# interface (`await _bookService.GetListAsync()`) without touching `HttpClient`. The proxies handle route/verb mapping, JSON (de)serialization, correlation id, current tenant/culture, API versioning, and error → exception translation. **Authentication is not automatic** — by default no token is attached (see *Authentication* below).

Both flavors need a **shared service interface** that extends `IRemoteService` — `IApplicationService` already does, so any app-service interface works. Put it in a shared project (typically `*.Application.Contracts`).

## When to Use

- Calling a remote ABP HTTP API from C# through its service interface.
- Choosing between dynamic (runtime) and static (build-time) client proxies.
- Pointing proxies at a `BaseUrl` (or named endpoint) via `AbpRemoteServiceOptions`.
- Wiring tiered / microservice calls where each service has its own endpoint.
- Adding retry/Polly policies to proxy HTTP clients.

## When Not to Use

- **Exposing your own application services as REST endpoints** — use the **expose-http-apis** skill.
- **Deciding whether the call should be synchronous HTTP or an asynchronous distributed event**, or setting up outbox/inbox — use the **design-module-and-service-communication** skill.
- **Routing the proxy calls through Dapr service invocation** — use the **integrate-dapr-services** skill.

## How it works

### Dynamic proxies (runtime)

Generated at runtime — easiest to develop, no re-generation step. Add `Volo.Abp.Http.Client` (`abp add-package Volo.Abp.Http.Client`), depend on `AbpHttpClientModule`, and register the proxies for an assembly:

```csharp
[DependsOn(
    typeof(AbpHttpClientModule),
    typeof(BookStoreApplicationContractsModule) // holds the service interfaces
)]
public class MyClientAppModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        context.Services.AddHttpClientProxies(
            typeof(BookStoreApplicationContractsModule).Assembly);
    }
}
```

`AddHttpClientProxies` scans the assembly, finds every `IRemoteService` interface, and registers a proxy for each. Full signature:

```csharp
AddHttpClientProxies(
    Assembly assembly,
    string remoteServiceConfigurationName = "Default", // RemoteServiceConfigurationDictionary.DefaultName
    bool asDefaultServices = true,
    ApplicationServiceTypes applicationServiceTypes = ApplicationServiceTypes.All)
```

### Static proxies (build-time)

Code is generated into your project at development time — a bit faster at runtime (no need to fetch the API definition), but you must **re-run the generator whenever the API changes**. Setup uses `AddStaticHttpClientProxies` plus the virtual file system for the generated `app-generate-proxy.json`:

```csharp
[DependsOn(
    typeof(AbpHttpClientModule),
    typeof(AbpVirtualFileSystemModule)
)]
public class MyClientAppModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        // With contracts (default): interfaces are generated into THIS client module,
        // so scan the client module's own assembly.
        context.Services.AddStaticHttpClientProxies(typeof(MyClientAppModule).Assembly);

        Configure<AbpVirtualFileSystemOptions>(options =>
        {
            options.FileSets.AddEmbedded<MyClientAppModule>();
        });
    }
}
```

`AddStaticHttpClientProxies` scans the assembly you pass for public `IRemoteService` interfaces, so **which assembly to pass depends on the contracts mode**:

- **With contracts** (default): the generator writes the interfaces/DTOs into this client module, so pass the **client module assembly** (`typeof(MyClientAppModule).Assembly`).
- **Without contracts** (`--without-contracts`): the interfaces come from the target's `*.Application.Contracts` (which you must depend on), so pass the **`Application.Contracts` assembly**:

```csharp
[DependsOn(
    typeof(AbpHttpClientModule),
    typeof(AbpVirtualFileSystemModule),
    typeof(BookStoreApplicationContractsModule) // holds the reused service interfaces
)]
public class MyClientAppModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        context.Services.AddStaticHttpClientProxies(
            typeof(BookStoreApplicationContractsModule).Assembly);

        Configure<AbpVirtualFileSystemOptions>(options =>
        {
            options.FileSets.AddEmbedded<MyClientAppModule>();
        });
    }
}
```

`AddStaticHttpClientProxies(Assembly, string remoteServiceConfigurationName = "Default", ApplicationServiceTypes = All)` — note there is **no** `asDefaultServices` parameter here (that one is dynamic-only).

Generate the code with the server running on the configured `BaseUrl`:

```bash
# With contracts (default): also generates interfaces/DTOs client-side
abp generate-proxy -t csharp -u http://localhost:53929/

# Without contracts: reuse the target's Application.Contracts package instead
abp generate-proxy -t csharp -u http://localhost:53929/ --without-contracts
```

Use `--without-contracts` when the client already references the target's `*.Application.Contracts` (so DTOs/interfaces are reused). Use *with* contracts for fully independent microservices that must not depend on the target's contracts package. Generated `*ClientProxy.Generated.cs` are `partial` — add custom code in a sibling partial and ABP won't overwrite it.

### Usage (identical for both)

Inject the interface — the proxy is the registered implementation:

```csharp
public class MyService : ITransientDependency
{
    private readonly IBookAppService _bookService;
    public MyService(IBookAppService bookService) => _bookService = bookService;

    public async Task DoItAsync()
    {
        var books = await _bookService.GetListAsync();
    }
}
```

If you registered dynamic proxies with `asDefaultServices: false` (e.g. a local implementation already exists and you don't want to replace it), inject `IHttpClientProxy<IBookAppService>` and call its `.Service` property instead.

### `AbpRemoteServiceOptions` & endpoints

The proxy's target address comes from the `RemoteServices` section of `appsettings.json`, bound to `AbpRemoteServiceOptions`:

```json
{
  "RemoteServices": {
    "Default":   { "BaseUrl": "http://localhost:53929/" },
    "BookStore": { "BaseUrl": "http://localhost:48392/" }
  }
}
```

`AbpRemoteServiceOptions.RemoteServices` is a `RemoteServiceConfigurationDictionary` (string → `RemoteServiceConfiguration`). Each `RemoteServiceConfiguration` exposes `BaseUrl` and optional `Version`. Configure/override it in code:

```csharp
context.Services.Configure<AbpRemoteServiceOptions>(options =>
{
    options.RemoteServices.Default =
        new RemoteServiceConfiguration("http://localhost:53929/");
});
```

### Tiered / microservice calls (named endpoints)

Give a proxy registration a named endpoint via `remoteServiceConfigurationName`; it maps to a key in the config above. If the named endpoint isn't defined, it falls back to `Default`:

```csharp
context.Services.AddHttpClientProxies(
    typeof(BookStoreApplicationContractsModule).Assembly,
    remoteServiceConfigurationName: "BookStore");
```

This is the standard pattern for microservices where each service (and the API gateway) has its own `BaseUrl`. To read a resolved config at runtime, inject `IRemoteServiceConfigurationProvider` and call `GetConfigurationOrDefaultAsync("BookStore")` (returns a `RemoteServiceConfiguration` with the `BaseUrl`).

### Authentication (not automatic)

By default the proxy attaches **no** auth token — the built-in `NullRemoteServiceHttpClientAuthenticator` does nothing, so a call to a `[Authorize]` endpoint gets **401** unless you wire authentication. Two patterns:

**Forward the current user's token (web host).** A web app calling a remote API on behalf of the signed-in user adds `Volo.Abp.Http.Client.IdentityModel.Web` and depends on `AbpHttpClientIdentityModelWebModule`; it takes the current request's access token and adds it as a bearer header. This is what the tiered Blazor/MVC startup templates use.

**Client credentials (server-to-server).** A back-end service calling another with its **own** identity (no user context) adds `Volo.Abp.Http.Client.IdentityModel` and depends on `AbpHttpClientIdentityModelModule`, then configures an `IdentityClients` entry (per named remote service) in `appsettings.json`:

```json
{
  "IdentityClients": {
    "Default": {
      "GrantType": "client_credentials",
      "ClientId": "MyApp_OrderService",
      "ClientSecret": "...",
      "Authority": "https://localhost:44322",
      "Scope": "ProductService"
    }
  }
}
```

Keep the `ClientSecret` out of source control — read it from user-secrets, an environment variable, or a secret store rather than committing it to `appsettings.json`.

The `IdentityClients` key matches the **named remote service** (`Default`, `BookStore`, …) used for the proxy. To force forwarding the current user's token for a specific named service, call `configuration.SetUseCurrentAccessToken(true)` on its `RemoteServiceConfiguration` — it's an extension method, not a property (the class itself exposes only `BaseUrl`/`Version`) — or set `"UseCurrentAccessToken": "true"` in the `RemoteServices` entry.

### Retry / Polly

**Only retry safe/idempotent requests.** A blind retry on a timed-out `POST`/create can duplicate the side effect, so scope the policy per named client (or per operation), require an idempotency key for commands, and add jitter. Configure `AbpHttpClientBuilderOptions` in `PreConfigureServices` (needs `Microsoft.Extensions.Http.Polly` and `using Polly;`):

```csharp
PreConfigure<AbpHttpClientBuilderOptions>(options =>
{
    options.ProxyClientBuildActions.Add((remoteServiceName, clientBuilder) =>
    {
        // Scope retry to a specific service whose calls are safe/idempotent, and add jitter.
        // Don't blanket-retry every client — a retried POST/create can duplicate the effect.
        if (remoteServiceName != "ReportingService")
        {
            return;
        }

        clientBuilder.AddTransientHttpErrorPolicy(builder =>
            builder.WaitAndRetryAsync(3, i =>
                TimeSpan.FromSeconds(Math.Pow(2, i))
                + TimeSpan.FromMilliseconds(Random.Shared.Next(0, 250))));
    });
});
```

## Validation

- Inject the service interface and make a call (e.g. `await _bookService.GetListAsync()`) against a running target host; a successful response confirms the proxy resolves the right `BaseUrl` and maps route/verb correctly.
- Confirm the `RemoteServices` section (or code config) contains the endpoint name the proxy was registered under; a missing named endpoint falls back to `Default`.
- For static proxies, re-run `abp generate-proxy` and confirm the `*ClientProxy.Generated.cs` files regenerate after an API change.

## Common Pitfalls

- Static proxies must be **re-generated whenever the target API changes**. Dynamic proxies need **no client code regeneration**, but a running client won't pick up a changed API at runtime either: the API definition is fetched once per `baseUrl` and held in the singleton `ApiDescriptionCache` with no refresh path, so restart the client to pick up API changes.
- `AddStaticHttpClientProxies` has **no** `asDefaultServices` parameter — that argument is dynamic-only.
- When `asDefaultServices: false`, the interface is not the default registration — inject `IHttpClientProxy<IBookAppService>` and use `.Service`.
- A named endpoint that isn't defined in config silently falls back to `Default`.
- Don't hand-edit generated `*ClientProxy.Generated.cs`; they're `partial`, so put custom code in a sibling partial that ABP won't overwrite.
- Polly retry needs the `Microsoft.Extensions.Http.Polly` package and `using Polly;`.
- **Assuming the proxy forwards auth automatically — it doesn't.** With only `AbpHttpClientModule`, no token is attached and a protected endpoint returns 401. Add an IdentityModel module (`AbpHttpClientIdentityModelWebModule` to forward the current user's token, or `AbpHttpClientIdentityModelModule` + `IdentityClients` for client credentials).
