---
name: define-application-modules
description: >
  Define and wire up an ABP module: the AbpModule class, [DependsOn] dependencies, service registration, options configuration, lifecycle hooks, and conventional DI.
  USE FOR: creating an AbpModule class, declaring [DependsOn] dependencies, registering services in ConfigureServices / PreConfigureServices / PostConfigureServices, configuring options with Configure for an options class, adding startup/shutdown lifecycle hooks (OnApplicationInitialization / OnApplicationShutdown), relying on ITransientDependency/IScopedDependency/ISingletonDependency conventional DI.
  DO NOT USE FOR: deciding which project a class belongs in or the overall solution layering (use layered-architecture); modeling entities/aggregates/value objects/domain services (use model-domain-aggregates); loading modules at runtime as plug-ins (use create-plugin-modules); writing application service implementations (use application-services).
license: MIT
---

# Defining ABP Modules

Every ABP application and reusable module is defined by a **module class** that derives from `AbpModule` (namespace `Volo.Abp.Modularity`). The module class is where you declare dependencies, register services, configure options, and run startup/shutdown logic. ABP builds the dependency graph from the root module and initializes/shuts down all modules in the correct order.

## When to Use

- Creating an `AbpModule` class for an application or reusable module.
- Declaring dependencies on other modules with `[DependsOn]`.
- Registering services in `ConfigureServices` (or `Pre`/`PostConfigureServices`).
- Configuring options with `Configure<TOptions>` and its Pre/Post variants.
- Adding startup/shutdown lifecycle hooks.
- Wiring up conventional DI via `ITransientDependency` / `IScopedDependency` / `ISingletonDependency`.

## When Not to Use

- **Deciding which project/layer a class belongs in** — use the layered-architecture skill.
- **Modeling entities, aggregate roots, value objects, or domain services** — use the model-domain-aggregates skill.
- **Loading modules at runtime as plug-ins** (`PlugInSources`) — use the create-plugin-modules skill.
- **Writing application service implementations** — use the application-services skill.

## How it works

### The Module Class

```csharp
using Volo.Abp.Modularity;

public class BlogModule : AbpModule
{
}
```

`AbpModule` is `abstract` and already implements all the lifecycle interfaces, so you only override the methods you need. Module classes are registered into DI as **singletons**.

### Declaring Dependencies with [DependsOn]

Declare only your **direct** dependencies; ABP resolves the transitive graph.

```csharp
[DependsOn(typeof(AbpAspNetCoreMvcModule))]
[DependsOn(typeof(AbpAutofacModule))]
public class BlogModule : AbpModule
{
}
```

You can use multiple `[DependsOn]` attributes or pass multiple types to one attribute. After `abp add-package <package>`, add the corresponding module type to `[DependsOn]` (the CLI does this for you).

### Service Registration & Options

`ConfigureServices` is the main place to register services and configure other modules. It receives a `ServiceConfigurationContext` whose `Services` property is the `IServiceCollection`.

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    // Manual registration when you need factories, instances or multiple impls:
    context.Services.AddTransient<IExternalLogger, AzureExternalLogger>();

    // Configure an options class (delegates to IServiceCollection.Configure):
    Configure<AbpDbConnectionOptions>(options =>
    {
        options.ConnectionStrings.Default = "...";
    });
}
```

`AbpModule` exposes `protected` option helpers that wrap the standard options system:
`Configure<TOptions>(...)`, `Configure<TOptions>(string name, ...)`, `Configure<TOptions>(IConfiguration)`, plus `PreConfigure<TOptions>`, `PostConfigure<TOptions>` and `PostConfigureAll<TOptions>`.

### Pre / Post Configure Services

`PreConfigureServices` runs before, and `PostConfigureServices` after, the `ConfigureServices` methods of **all** modules. Use `PreConfigureServices` for things other modules must see early (e.g. `context.Services.OnRegistered(...)` interceptor hooks, or `PreConfigure<IMvcBuilder>(...)`).

```csharp
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    context.Services.OnRegistered(ctx =>
    {
        // e.g. attach an interceptor to matching service types
    });
}
```

### Async Versions

Each of these has an async counterpart: `ConfigureServicesAsync`, `PreConfigureServicesAsync`, `PostConfigureServicesAsync`. Override the async version **only** when you need `await` inside. `AbpModule`'s default async implementation calls the sync one, so on an async startup path (`CreateAsync` / `InitializeAsync`) the async method runs, while a synchronous startup (`Create` / `Initialize`) runs the sync method directly. If you override only the async version, the synchronous startup path skips your custom logic — override both (or the sync version) if the app may start either way. The same rule applies to all lifecycle methods below.

### Application Lifecycle Hooks

Once all services are configured, ABP initializes modules. At this point `IServiceProvider` is ready, so you can resolve services.

```csharp
public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var myService = context.ServiceProvider.GetRequiredService<MyService>();
    myService.DoSomething();
}
```

The startup module typically builds the ASP.NET Core middleware pipeline here:

```csharp
public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();
    var env = context.GetEnvironment();

    if (env.IsDevelopment())
    {
        app.UseDeveloperExceptionPage();
    }

    app.UseConfiguredEndpoints();
}
```

Available hooks (each with an `...Async` counterpart, receiving `ApplicationInitializationContext` or `ApplicationShutdownContext`):

- `OnPreApplicationInitialization` — before `OnApplicationInitialization` of all modules
- `OnApplicationInitialization` — main initialization
- `OnPostApplicationInitialization` — after all modules initialized
- `OnApplicationShutdown` — cleanup on shutdown

### Conventional Dependency Injection

ABP scans the **main assembly** (the assembly that defines the module class) and auto-registers services. Some base types are registered by convention (e.g. application services deriving from `ApplicationService` and domain services deriving from `DomainService` register as **transient**).

For your own classes, implement a lifetime interface (namespace `Volo.Abp.DependencyInjection`):

```csharp
public class TaxCalculator : ITransientDependency { }  // transient
public class CacheManager  : ISingletonDependency { }  // singleton
public class RequestState  : IScopedDependency { }     // scoped
```

By convention a class exposes **itself** plus its **default interfaces** (interfaces whose name matches by convention, e.g. `TaxCalculator` → `ITaxCalculator`). Use `[ExposeServices(...)]` to restrict, and `[Dependency(...)]` (`Lifetime`, `TryRegister`, `ReplaceServices`) for finer control.

### Additional & Skipped Registration

- Set `SkipAutoServiceRegistration = true` in the module constructor to disable auto-scanning; then register manually, e.g. `context.Services.AddAssemblyOf<BlogModule>()`.
- Use `[AdditionalAssembly(typeof(SomeTypeInOtherAssembly))]` on the module only in the rare case a single module spans multiple assemblies. Prefer a separate module + `[DependsOn]` instead.

## The options pattern (producer + consumer)

ABP builds on `Microsoft.Extensions.Options`. A **producer** module defines a plain options class and lets dependents configure it; a **consumer** injects `IOptions<TOptions>` and reads `.Value` at runtime.

### Configure and consume

Define a plain class (the producer's contract), let any dependent module set it in `ConfigureServices`, and read it where you need it:

```csharp
public class BlogOptions
{
    public int PageSize { get; set; }
    public bool EnableComments { get; set; }
}

// Any dependent module, in ConfigureServices:
public override void ConfigureServices(ServiceConfigurationContext context)
{
    Configure<BlogOptions>(options =>
    {
        options.PageSize = 25;
        options.EnableComments = true;
    });
}
```

`Configure<TOptions>(...)` is the `AbpModule` shortcut for `context.Services.Configure<TOptions>(...)` (both work). Consume at runtime by injecting `IOptions<TOptions>` and reading its `.Value`:

```csharp
public class BlogService : ITransientDependency
{
    private readonly BlogOptions _options;

    public BlogService(IOptions<BlogOptions> options)
    {
        _options = options.Value; // resolved value, valid after ConfigureServices completes
    }
}
```

`IOptions<TOptions>` is a singleton with a fixed snapshot; use `IOptionsSnapshot<TOptions>` (scoped) or `IOptionsMonitor<TOptions>` when you need reload-aware or per-scope values — same as standard .NET.

### Pre-configuration: influencing options before DI is finalized

`IOptions<TOptions>.Value` is only readable **after** all modules' `ConfigureServices` complete. But a producer module sometimes needs option values **during** registration — to decide what to register or how to wire other services. That's what pre-configuration is for.

The producer exposes a *pre-options* class. Dependents set it in `PreConfigureServices` with `PreConfigure<TOptions>(...)`, and the producer reads the accumulated values back in its own `ConfigureServices` via `context.Services.ExecutePreConfiguredActions<TOptions>()`:

```csharp
public class MyPreOptions
{
    public bool MyValue { get; set; }
}

// A dependent module — runs first because PreConfigureServices precedes ConfigureServices:
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    PreConfigure<MyPreOptions>(options =>
    {
        options.MyValue = true;
    });
}

// The producer module reads them back while still registering services:
public override void ConfigureServices(ServiceConfigurationContext context)
{
    var options = context.Services.ExecutePreConfiguredActions<MyPreOptions>();
    if (options.MyValue)
    {
        // register/wire services based on the pre-configured value
    }
}
```

`PreConfigure<TOptions>(this IServiceCollection, Action<TOptions>)` and `ExecutePreConfiguredActions<TOptions>(this IServiceCollection)` are extension methods in `Microsoft.Extensions.DependencyInjection` (defined in `Volo.Abp.Core`; `ExecutePreConfiguredActions<TOptions>` requires `TOptions : new()`). `ExecutePreConfiguredActions` returns a fresh `TOptions` with every registered pre-config action applied in order.

**Ordering that makes this work:** across *all* modules, ABP runs every `PreConfigureServices` before any `ConfigureServices`. So the pre-config actions dependents register have all run by the time the producer calls `ExecutePreConfiguredActions` in its `ConfigureServices`. Multiple modules can pre-configure the same options and override each other's values based on their `[DependsOn]` order. A module exposes pre-config precisely so dependents can influence a decision the module makes at registration time, before the option is finalized.

## Application startup (bootstrapping the ABP system)

Module classes describe *what* gets configured; something outside them has to *create* the ABP application container and *initialize* the modules. That's `AbpApplicationFactory` (namespace `Volo.Abp`).

### Creating the container

`AbpApplicationFactory.CreateAsync<TStartupModule>()` (or `Create<TStartupModule>()` when you can't `await`) builds the container from a single **root/startup module**; every other module is pulled in as its `[DependsOn]` dependency. In a minimal console app you own the full lifecycle:

```csharp
using var application = await AbpApplicationFactory.CreateAsync<MyConsoleDemoModule>();
await application.InitializeAsync();          // create service provider + initialize all modules
// ... use application.ServiceProvider ...
await application.ShutdownAsync();
```

`CreateAsync` runs all modules' `PreConfigureServices` / `ConfigureServices` / `PostConfigureServices`; `InitializeAsync()` builds the service provider and runs the initialization lifecycle hooks. `AbpApplicationFactory` has overloads taking the module as a `Type`, and overloads taking an external `IServiceCollection`.

### Internal vs external service provider

The overload distinction is real in the type system:

- `CreateAsync<TStartupModule>()` (no `IServiceCollection`) returns `Task<IAbpApplicationWithInternalServiceProvider>` — ABP owns the `IServiceCollection` and builds the `IServiceProvider` itself. Its `InitializeAsync()` takes no argument. (The synchronous `Create<TStartupModule>()` returns the non-`Task` `IAbpApplicationWithInternalServiceProvider`.)
- `CreateAsync<TStartupModule>(IServiceCollection services)` returns `Task<IAbpApplicationWithExternalServiceProvider>` — you (or a host framework) own DI. You build the provider (`services.BuildServiceProviderFromFactory()`) and hand it in: `InitializeAsync(serviceProvider)`.

### Hosted (framework-managed) vs manually-managed lifetime

In a console/standalone app you call `InitializeAsync()` / `ShutdownAsync()` yourself. In an ASP.NET Core (or .NET Generic Host) app the host manages the lifetime for you:

- `services.AddApplicationAsync<TStartupModule>(...)` (extension in `Microsoft.Extensions.DependencyInjection`, returns `Task<IAbpApplicationWithExternalServiceProvider>`) registers the container against the host's `IServiceCollection` during service configuration.
- `app.InitializeApplicationAsync()` (an `IApplicationBuilder` extension in the `Microsoft.AspNetCore.Builder` namespace, shipped by the `Volo.Abp.AspNetCore` package) initializes the modules **and** registers shutdown with `IHostApplicationLifetime` — `ApplicationStopping` triggers `ShutdownAsync()` and `ApplicationStopped` disposes the app. You don't call `ShutdownAsync` yourself; the host does. Templates generated by `abp new` wire this for you, so you rarely touch it directly.

`AbpApplicationFactory` returns an `IAbpApplication`, which is itself registered in DI and disposable — always dispose it before the process exits (the `using var` above, or the host's `ApplicationStopped` in the managed case).

## Validation

- Derive from `AbpModule`; add `[DependsOn]` for each package you install.
- Register services in `ConfigureServices`; configure options with `Configure<TOptions>`.
- Use `Pre/PostConfigureServices` for cross-module ordering.
- Prefer `ITransientDependency` / `IScopedDependency` / `ISingletonDependency` over manual registration for your own services.
- The app boots and modules initialize in dependency order — verify a service registered in one module is resolvable from `context.ServiceProvider` in a dependent module's `OnApplicationInitialization`.

## Common Pitfalls

- **Overriding only the async lifecycle method** (e.g. `ConfigureServicesAsync`) when the app may start on a synchronous path — the sync path skips your custom logic. Override both (or the sync version) unless you're certain of the startup path.
- **Accessing `ServiceConfigurationContext` outside `Pre/Post/ConfigureServices`** — it is only available inside those methods and throws elsewhere.
- **Declaring transitive dependencies in `[DependsOn]`** — declare only direct dependencies; ABP resolves the rest.
- **Manually registering your own services** when a lifetime interface (`ITransientDependency` etc.) would do — prefer convention.
