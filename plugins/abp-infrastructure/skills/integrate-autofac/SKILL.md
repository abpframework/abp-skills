---
name: integrate-autofac
description: "Replace the default Microsoft DI provider with ABP's Autofac integration. USE FOR: AbpAutofacModule, UseAutofac on IHostBuilder / AbpApplicationCreationOptions, property injection and Castle interception. DO NOT USE FOR: implementing/debugging interceptors (use-interceptors-and-dynamic-proxy); registering/replacing/decorating services (register-and-replace-services); module lifecycle config (define-application-modules)."
license: MIT
---

# Integrating Autofac with ABP

## When to Use

- Replace the built-in Microsoft DI service provider in an ABP host.
- Add the container prerequisite for ABP's Autofac/Castle dynamic proxies.
- Enable ABP convention-based property injection for module assemblies.
- Configure a non-hosted or test ABP application to use Autofac.

## When Not to Use

- **Select, implement, or debug interceptors** — use use-interceptors-and-dynamic-proxy.
- **Register, replace, expose, key, or decorate services** — use register-and-replace-services.
- **Define module dependencies or lifecycle hooks generally** — use define-application-modules.

## Workflow

### 1. Depend on the Autofac module

Add `Volo.Abp.Autofac` and declare the module dependency:

```csharp
[DependsOn(typeof(AbpAutofacModule))]
public class MyAppModule : AbpModule
{
}
```

`AbpAutofacModule` is intentionally thin. It depends on `AbpCastleCoreModule`, which supplies the Castle integration used by ABP interceptors.

### 2. Replace the host service provider

For a generic/ASP.NET Core host, call ABP's `IHostBuilder` extension before adding the ABP application:

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Host
    .UseAutofac();

await builder.AddApplicationAsync<MyAppModule>();
```

The extension creates a `ContainerBuilder`, exposes it through the service collection, and installs `AbpAutofacServiceProviderFactory` with `UseServiceProviderFactory(...)`.

For `AbpApplicationFactory` or another direct ABP application creation path, use the creation options:

```csharp
var application = await AbpApplicationFactory.CreateAsync<MyAppModule>(options =>
{
    options.UseAutofac();
});
```

This overload adds a `ContainerBuilder` object accessor and registers the factory as `IServiceProviderFactory<ContainerBuilder>`.

### 3. Let the factory populate and build Autofac

`AbpAutofacServiceProviderFactory.CreateBuilder` calls `ContainerBuilder.Populate(IServiceCollection)`. `CreateServiceProvider` builds the container and returns `AutofacServiceProvider`.

During population, ABP conventions:

- enable property injection for implementation types whose assemblies belong to the loaded module chain (`IAbpModuleDescriptor.AllAssemblies`), unless the class or property disables it;
- run ABP service registration actions and attach configured interceptors;
- preserve Microsoft DI service descriptors, lifetimes, and keyed-service exposure through the Autofac adapter.

This skill stops at container setup. Use the dedicated sibling skills to define service registrations or interceptor selection.

### 4. Verify container access only after setup

`services.GetContainerBuilder()` returns the registered builder. It throws `AbpException` with a message instructing callers to invoke `UseAutofac` when the builder is missing. Do not use this as the normal place for ABP service registration when `IServiceCollection` conventions are sufficient.

## Validation

- Resolve `IServiceProvider` after startup and confirm it is backed by `AutofacServiceProvider`.
- Confirm `services.GetContainerBuilder()` succeeds after `UseAutofac` and fails without it.
- Resolve a conventionally registered type from an ABP module assembly and verify an injectable property is populated.
- Run one existing intercepted ABP service through DI to confirm the container prerequisite is present; diagnose interceptor rules with use-interceptors-and-dynamic-proxy.
- Build and start the host so the service-provider factory path is exercised, not merely compiled.

## Common Pitfalls

- **Adding only `AbpAutofacModule`** — the module dependency does not replace the host service provider; also call the appropriate `UseAutofac()` overload.
- **Calling the wrong overload for the startup model** — use `IHostBuilder.UseAutofac()` for hosted apps and `AbpApplicationCreationOptions.UseAutofac()` for direct application creation.
- **Calling `UseAutofac()` after the service provider has already been built** — install the factory during host/application construction.
- **Assuming Autofac makes every method interceptable** — proxy selection and virtual/interface rules belong to use-interceptors-and-dynamic-proxy.
- **Using property injection as the default design** — constructor injection remains clearer for required dependencies; Autofac support only makes ABP property injection available.
