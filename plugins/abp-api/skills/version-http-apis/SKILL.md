---
name: version-http-apis
description: >
  Add API versioning to ABP HTTP APIs so multiple versions of the same service coexist behind static client proxies.
  USE FOR: AddAbpApiVersioning, query/header/media-type version readers, attaching ApiVersions to conventional controllers, ICurrentApiVersionInfo runtime version switching, the versioned API explorer.
  DO NOT USE FOR: exposing services as controllers in the first place (use expose-http-apis); Swagger UI / OpenAPI doc setup (use configure-swagger-openapi); generating or calling C# client proxies (use consume-remote-services).
license: MIT
---

# Version ABP HTTP APIs

ABP integrates the [ASP.NET API Versioning](https://github.com/dotnet/aspnet-api-versioning/wiki)
library and adapts it to Auto (Conventional) API Controllers and the static C# / JavaScript
client proxies. You enable it once, then either attach versions per controller (attribute
routing) or per assembly (conventional controllers).

## When to Use

- Serving `1.0` and `2.0` (etc.) of the same service side by side.
- Attaching versions to conventional controllers via `ConventionalControllers.Create(...)`.
- Switching the requested version from C# at runtime with `ICurrentApiVersionInfo`.
- Building one Swagger document per discovered version.

## When Not to Use

- **Just exposing a service as a controller** (no versions yet) — use **expose-http-apis**.
- **Swagger UI / OpenAPI wiring** beyond the versioned explorer — use **configure-swagger-openapi**.
- **Generating or calling client proxies** — use **consume-remote-services**.

## ⚠️ Read this first: URL-path versioning breaks the static proxies

The static C# and JavaScript client proxies **cannot** carry the version in the URL path/segment.
Use **query-string versioning** (`?api-version=2.0`) — the default ABP proxies emit.

Grounding: `ApiVersionInfo.ShouldSendInQueryString()` returns `!BindingSource.IsIn("Path")`
(`framework/src/Volo.Abp.Http.Client/Volo/Abp/Http/Client/ClientProxying/ApiVersionInfo.cs`),
so a `Path` binding source is never appended to the proxy request. The versioning doc says the
same: this feature "does not compatible with URL Path Versioning, we suggest to use Versioning
via the Query String" (`docs/en/framework/api-development/versioning.md`).

## Enable versioning

`AddAbpApiVersioning` is an `IServiceCollection` extension in `Microsoft.Extensions.DependencyInjection`
(`framework/src/Volo.Abp.AspNetCore.Mvc/.../AbpApiVersioningExtensions.cs`). Its signature:

```csharp
IApiVersioningBuilder AddAbpApiVersioning(
    this IServiceCollection services,
    Action<ApiVersioningOptions>? apiVersioningOptionsSetupAction = null,
    Action<MvcApiVersioningOptions>? mvcApiVersioningOptionsSetupAction = null)
```

`ApiVersioningOptions` / `MvcApiVersioningOptions` and the properties set below
(`ReportApiVersions`, `AssumeDefaultVersionWhenUnspecified`) come from the ASP.NET API
Versioning library — they are **not** ABP types. Same for `IApiControllerFilter` /
`NoControllerFilter` (used to keep neutral/versionless APIs visible).

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    // Show neutral / versionless APIs.
    context.Services.AddTransient<IApiControllerFilter, NoControllerFilter>();

    context.Services.AddAbpApiVersioning(options =>
    {
        options.ReportApiVersions = true;
        options.AssumeDefaultVersionWhenUnspecified = true;
    });

    Configure<AbpAspNetCoreMvcOptions>(options =>
    {
        options.ChangeControllerModelApiExplorerGroupName = false;
    });
}
```

The version reader (query string vs. header vs. media type) is the standard ASP.NET API
Versioning `ApiVersionReader` on `ApiVersioningOptions` — keep it on the query string when static
proxies are in play (see the warning above).

## Attribute-routed controllers

Put `[ApiVersion(...)]` (an ASP.NET API Versioning attribute) on each controller. Two controllers
sharing one `[Route]` but different versions serve as v1/v2 of the same service:

```csharp
[ApiVersion("1.0", Deprecated = true)]
[ControllerName("Book")]
[Route("api/BookStore/Book")]
public class BookController : BookStoreController, IBookAppService { /* ... */ }

[ApiVersion("2.0")]
[ControllerName("Book")]
[Route("api/BookStore/Book")]
public class BookV2Controller : BookStoreController, IBookV2AppService { /* ... */ }
```

## Conventional (Auto API) controllers

Attach versions per assembly in `PreConfigureServices`. `ConventionalControllerSetting.ApiVersions`
is a `List<ApiVersion>` (`framework/src/Volo.Abp.AspNetCore.Mvc/.../Conventions/ConventionalControllerSetting.cs`);
`ApiVersion` is an ASP.NET API Versioning type. Use `TypePredicate` to split versions by namespace:

```csharp
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    PreConfigure<AbpAspNetCoreMvcOptions>(options =>
    {
        options.ConventionalControllers.Create(typeof(BookStoreWebAppModule).Assembly, opts =>
        {
            opts.TypePredicate = t => t.Namespace == typeof(v2.TodoAppService).Namespace;
            opts.ApiVersions.Add(new ApiVersion(2, 0));
        });

        options.ConventionalControllers.Create(typeof(BookStoreWebAppModule).Assembly, opts =>
        {
            opts.TypePredicate = t => t.Namespace == typeof(v1.TodoAppService).Namespace;
            opts.ApiVersions.Add(new ApiVersion(1, 0));
        });
    });
}
```

Then wire those pre-configured settings into the versioning options with the `ConfigureAbp`
extension — `ConfigureAbp(this MvcApiVersioningOptions options, AbpAspNetCoreMvcOptions mvcOptions)`
(same file as `AddAbpApiVersioning`). It reads `mvcOptions.ConventionalControllers`, calling each
setting's `MvcApiVersioningConfigurer` if set, otherwise applying its `ApiVersions` by convention
(neutral when none):

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    var preActions = context.Services.GetPreConfigureActions<AbpAspNetCoreMvcOptions>();

    context.Services.AddTransient<IApiControllerFilter, NoControllerFilter>();
    context.Services.AddAbpApiVersioning(options =>
    {
        options.ReportApiVersions = true;
        options.AssumeDefaultVersionWhenUnspecified = true;
    }, options =>
    {
        options.ConfigureAbp(preActions.Configure());
    });
}
```

## Switch the requested version at runtime (C#)

When one client wants a specific version from a multi-version service, inject
`ICurrentApiVersionInfo` (`namespace Volo.Abp.Http.Client.ClientProxying`) and scope the change
with `Change(...)`. It stores an `AsyncLocal` value restored on dispose, so wrap it in a `using`:

```csharp
var current = serviceProvider.GetRequiredService<ICurrentApiVersionInfo>();
var bookService = serviceProvider.GetRequiredService<IBookV4AppService>();

using (current.Change(new ApiVersionInfo(ParameterBindingSources.Query, "4.0")))
{
    var book = await bookService.GetAsync(); // proxy adds ?api-version=4.0
}
```

- `ApiVersionInfo(string bindingSource, string version)` —
  `framework/src/Volo.Abp.Http.Client/.../ClientProxying/ApiVersionInfo.cs`.
- `ParameterBindingSources.Query` / `.Header` / `.Path` … are string consts in
  `Volo.Abp.Http.ProxyScripting.Generators.ParameterBindingSources`. Use `Query`; `Path` is
  dropped by the proxy (see the warning).

## Versioned API explorer / Swagger

Chain `.AddApiExplorer(...)` on the builder returned by `AddAbpApiVersioning` for one Swagger
document per version, then iterate `provider.ApiVersionDescriptions` to add a `SwaggerEndpoint`
each. `GroupNameFormat`, `SubstituteApiVersionInUrl`, `IApiVersionDescriptionProvider` are ASP.NET
API Versioning types (not ABP); full example in the versioning doc. Deeper Swagger setup belongs
to the **configure-swagger-openapi** skill.

## Validation

- Call the same route with `?api-version=1.0` and `?api-version=2.0`; confirm each hits the
  matching version and that `ReportApiVersions` adds `api-supported-versions` response headers.
- Confirm neutral/versionless endpoints still appear (that's the `NoControllerFilter` job).
- With generated static proxies, confirm the request carries the version on the **query string**,
  not the path.

## Common Pitfalls

- **URL-path/segment versioning silently breaks static proxies** — the proxy never sends a `Path`
  binding source. Stay on query-string versioning.
- Setting `ApiVersions` on a conventional-controller assembly does nothing unless
  `options.ConfigureAbp(preActions.Configure())` is applied to the versioning options.
- `AddAbpApiVersioning` returns an `IApiVersioningBuilder`; call `.AddApiExplorer(...)` on that
  return value — don't try to add the explorer separately.
- `ReportApiVersions`, `AssumeDefaultVersionWhenUnspecified`, `[ApiVersion]`, `ApiVersion`,
  `IApiControllerFilter`/`NoControllerFilter` are ASP.NET API Versioning symbols ABP wraps — look
  them up in that library's wiki, not the ABP API.
