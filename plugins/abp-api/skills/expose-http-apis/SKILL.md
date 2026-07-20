---
name: expose-http-apis
description: >
  Expose ABP application services as REST endpoints through Auto/Conventional API Controllers.
  USE FOR: publishing application services as HTTP controllers, route/verb conventions, [RemoteService] toggles, integration services and [IntegrationService].
  DO NOT USE FOR: calling a remote ABP HTTP API from C# with client proxies (use consume-remote-services); designing sync-vs-async inter-service communication or the outbox/inbox (use design-module-and-service-communication); building UI pages (use angular-ui / blazor-ui / mvc-razor-ui).
license: MIT
---

# Expose ABP Services over HTTP

ABP turns application services into REST API controllers automatically by convention. You almost never write controllers by hand.

## When to Use

- Publishing an assembly's application services as REST endpoints via Auto (Conventional) API Controllers.
- Understanding or customizing the route and HTTP-verb conventions ABP derives from method names.
- Toggling exposure/metadata of a service with `[RemoteService]`.
- Exposing an inter-module / inter-microservice `[IntegrationService]` over HTTP.

## When Not to Use

- **Calling a remote ABP API from C#** (client proxies, `AbpRemoteServiceOptions`, named endpoints) — use the **consume-remote-services** skill.
- **Deciding whether two services should talk synchronously or asynchronously**, or setting up the outbox/inbox — use the **design-module-and-service-communication** skill.
- **Building UI** (Blazor/Angular/MVC pages) — use **angular-ui** / **blazor-ui** / **mvc-razor-ui**.

## How it works

### Auto (Conventional) API Controllers

Any class that implements `IRemoteService` becomes a candidate. `IApplicationService` inherits `IRemoteService`, so every application service qualifies. To publish the services in an assembly, configure `AbpAspNetCoreMvcOptions` in `PreConfigureServices`:

```csharp
[DependsOn(typeof(BookStoreApplicationModule))]
public class BookStoreWebModule : AbpModule
{
    public override void PreConfigureServices(ServiceConfigurationContext context)
    {
        PreConfigure<AbpAspNetCoreMvcOptions>(options =>
        {
            options.ConventionalControllers
                .Create(typeof(BookStoreApplicationModule).Assembly);
        });
    }
}
```

`Create` takes an optional setup action for per-assembly options (see below). Call it multiple times for different assemblies or option sets.

### Route & HTTP-verb conventions

Routes: `/api` + root path (default `/app`) + normalized service name (kebab-case, with `AppService`/`ApplicationService`/`Service` postfix removed) + `/{id}` when the method has an `id` parameter + the normalized action name.

HTTP method is picked from the method-name prefix:

| Prefix | Verb |
| --- | --- |
| `GetList` / `GetAll` / `Get` | GET |
| `Put` / `Update` | PUT |
| `Delete` / `Remove` | DELETE |
| `Create` / `Add` / `Insert` / `Post` | POST |
| `Patch` | PATCH |
| anything else | POST (default) |

Examples with the default `/app` root path:

| Method | Verb | Route |
| --- | --- | --- |
| `GetAsync(Guid id)` | GET | `/api/app/book/{id}` |
| `GetListAsync()` | GET | `/api/app/book` |
| `CreateAsync(CreateBookDto input)` | POST | `/api/app/book` |
| `UpdateAsync(Guid id, UpdateBookDto input)` | PUT | `/api/app/book/{id}` |
| `DeleteAsync(Guid id)` | DELETE | `/api/app/book/{id}` |

Override any of this with the standard ASP.NET Core attributes (`[HttpGet]`, `[HttpPost]`, `[Route]`, …). That requires the `Microsoft.AspNetCore.Mvc.Core` package in the service project.

### Per-assembly options

```csharp
options.ConventionalControllers.Create(
    typeof(BookStoreApplicationModule).Assembly,
    opts =>
    {
        opts.RootPath = "book-store";          // /api/book-store/...
        opts.TypePredicate = type => true;     // filter which types become controllers
        opts.UrlControllerNameNormalizer = ctx => ctx.ControllerName; // customize service name
        opts.UrlActionNameNormalizer = ctx => ctx.ActionNameInUrl;    // customize action name
        // opts.UseV3UrlStyle = true;          // pre-4.0 camelCase routes (kebab-case is default)
    });
```

### `[RemoteService]`

`RemoteServiceAttribute` toggles whether a class is exposed and whether it appears in API metadata (Swagger):

```csharp
[RemoteService(IsEnabled = false)]          // or [RemoteService(false)] — not exposed at all
public class PersonAppService : ApplicationService { }

[RemoteService(IsMetadataEnabled = false)]  // callable, but hidden from API Explorer/Swagger
public class HiddenAppService : ApplicationService { }

[RemoteService(Name = "abp")]               // set the remote service name for the controller
public class SomeController : AbpController { }
```

### Integration Services

An *integration service* is an application service meant for inter-module / inter-microservice calls rather than UI clients. Mark it with `[IntegrationService]` (from `Volo.Abp`), on the class or its interface:

```csharp
[IntegrationService]
public class ProductAppService : ApplicationService, IProductAppService { }

// or on the interface — then you don't need it on the class:
[IntegrationService]
public interface IProductAppService : IApplicationService { }
```

By convention, integration services:

- Are **not exposed** by default (security). URL prefix becomes `/integration-api` instead of `/api` when they are exposed via Auto API Controllers.
- Have **audit logging disabled** by default.

Expose them explicitly only when needed (e.g. a microservice consumed over a private network):

```csharp
Configure<AbpAspNetCoreMvcOptions>(options =>
{
    options.ExposeIntegrationServices = true;
});

Configure<AbpAuditingOptions>(options =>
{
    options.IsEnabledForIntegrationServices = true; // opt back into audit logging
});
```

Filter which kind of service an assembly's controllers cover with `ApplicationServiceTypes` (a `[Flags]` enum: `ApplicationServices`, `IntegrationServices`, `All`):

```csharp
options.ConventionalControllers.Create(
    typeof(MyApplicationModule).Assembly,
    setting => setting.ApplicationServiceTypes = ApplicationServiceTypes.IntegrationServices);
```

## Validation

- Run the host and open `/api/abp/api-definition`: the application services registered via `ConventionalControllers.Create(...)` appear with the expected routes/verbs from the tables above.
- Hit an endpoint (e.g. `GET /api/app/book`) and confirm the route matches the convention or your overriding attribute.
- For integration services, confirm they do **not** appear until `ExposeIntegrationServices = true`, and that they then serve under `/integration-api` instead of `/api`.

## Common Pitfalls

- Overriding routes/verbs with ASP.NET Core attributes (`[HttpGet]`, `[Route]`, …) requires the `Microsoft.AspNetCore.Mvc.Core` package in the service project.
- Integration services are **not exposed** by default and have **audit logging disabled** by default. To expose them set `ExposeIntegrationServices = true` (that's all exposing requires — it controls whether the integration controllers are removed). `IsEnabledForIntegrationServices` is a separate opt-in that only re-enables auditing for them; you don't need it to expose the service.
- If you add API versioning, prefer **query-string versioning**; URL-path versioning is not compatible with the static client proxies.
