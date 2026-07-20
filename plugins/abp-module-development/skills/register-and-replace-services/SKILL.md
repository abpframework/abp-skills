---
name: register-and-replace-services
description: >
  Apply ABP's advanced dependency-injection conventions and controlled service customization.
  USE FOR: precise conventional exposure and lifetime rules; ExposeServices and Dependency attributes; replacing registrations; OnExposing, OnRegistered, and OnActivated callbacks; LazyServiceProvider/IAbpLazyServiceProvider; IObjectAccessor; keyed or string-named services; preserving lifetimes while decorating a service.
  DO NOT USE FOR: defining an AbpModule, its dependencies, and basic lifecycle or lifetime-marker registration (use define-application-modules); adding cross-cutting method interception (use use-interceptors-and-dynamic-proxy); replacing services specifically inside an installed pre-built module together with its entity/UI extensions (use customize-application-modules).
license: MIT
---

# Registering and Replacing Services

ABP builds on `IServiceCollection`: conventional registrars choose a lifetime and exposed service types, while attributes and registration callbacks let a module change those choices. Use constructor injection for normal dependencies; use the advanced mechanisms here only when exposure, replacement, late resolution, keys, activation hooks, or decoration requires them.

## When to Use

- Restrict or expand which service types a conventionally registered class exposes.
- Replace an existing interface/base-class registration without editing the original module.
- Observe or modify service exposure and registration during assembly scanning.
- Resolve optional services lazily or pass an object into startup/runtime code through `IObjectAccessor<T>`.
- Register several implementations under keys, including string keys used as names.
- Wrap an existing implementation while preserving its registered lifetime.

## When Not to Use

- **Create a module or learn its lifecycle/basic DI markers** — use define-application-modules.
- **Attach method interceptors** — use use-interceptors-and-dynamic-proxy.
- **Customize a packaged module across entity, DTO, service, and UI extension points** — use customize-application-modules.

## How it works

### Conventional registration and default exposure

`ITransientDependency`, `IScopedDependency`, and `ISingletonDependency` select the lifetime. Without an explicit exposure provider, ABP exposes the implementation type itself plus matching default interfaces. A default interface is one whose name matches the implementation suffix, ignoring an initial `I` and generic arity.

```csharp
public interface IInvoiceCalculator
{
    decimal Calculate(decimal netAmount);
}

public class InvoiceCalculator : IInvoiceCalculator, ITransientDependency
{
    public decimal Calculate(decimal netAmount) => netAmount;
}
```

This exposes `InvoiceCalculator` and `IInvoiceCalculator`. An unrelated implemented interface is not a default service unless explicitly exposed.

### Control exposure with `[ExposeServices]`

```csharp
[ExposeServices(typeof(IInvoiceCalculator))]
public class InvoiceCalculator : IInvoiceCalculator, ITransientDependency
{
    public decimal Calculate(decimal netAmount) => netAmount;
}
```

An explicit `[ExposeServices]` replaces default exposure unless `IncludeDefaults = true`; set `IncludeSelf = true` when the concrete class must also resolve. Multiple attributes are allowed.

### Control lifetime, try-add, and replacement

`[Dependency]` has `Lifetime`, `TryRegister`, and `ReplaceServices`. The conventional registrar applies them in this order: replace, try-add, otherwise add.

```csharp
[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(IInvoiceCalculator))]
public class DiscountInvoiceCalculator : IInvoiceCalculator, ITransientDependency
{
    public decimal Calculate(decimal netAmount) => netAmount * 0.9m;
}
```

The imperative equivalent is useful when the replacement is selected by configuration:

```csharp
context.Services.Replace(
    ServiceDescriptor.Transient<IInvoiceCalculator, DiscountInvoiceCalculator>());
```

Match the old lifetime unless there is a reviewed reason to change it. `Replace` replaces the first descriptor with the same service type; inspect the collection when multiple registrations are intentional.

### Registration callbacks

Install callbacks in `PreConfigureServices` so they observe conventionally scanned services.

```csharp
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    context.Services.OnExposing(exposingContext =>
    {
        if (typeof(IInternalService).IsAssignableFrom(exposingContext.ImplementationType))
        {
            exposingContext.ExposedTypes.RemoveAll(
                service => service.ServiceType == exposingContext.ImplementationType);
        }
    });

    context.Services.OnRegistered(registrationContext =>
    {
        // Inspect ImplementationType and ServiceKey here.
        // Add IAbpInterceptor types only when method interception is intended.
    });
}
```

- `OnExposing` runs while conventional exposure is being built; its mutable `ExposedTypes` contains `ServiceIdentifier` entries.
- `OnRegistered` receives `ImplementationType`, `ServiceKey`, and the interceptor type list. Use use-interceptors-and-dynamic-proxy before adding interceptors.
- `OnActivated(descriptor, callback)` is descriptor-specific. With the Autofac integration, its callback receives the created `Instance`; it observes activation but does not replace that instance.

### Lazy resolution

ABP has no `ILazyServiceProvider` type. ABP base classes expose a property named `LazyServiceProvider` whose type is `IAbpLazyServiceProvider`:

```csharp
var clock = LazyServiceProvider.LazyGetRequiredService<IClock>();
```

`IAbpLazyServiceProvider` remains for compatibility; its own source recommends `ITransientCachedServiceProvider` for new code. Both are cached service providers: the first resolution is stored, including transient services, for that provider instance.

```csharp
public class ReportBuilder : ITransientDependency
{
    private readonly ITransientCachedServiceProvider _services;

    public ReportBuilder(ITransientCachedServiceProvider services)
    {
        _services = services;
    }

    public IOptionalFormatter? GetFormatter()
    {
        return _services.GetService<IOptionalFormatter>();
    }
}
```

Prefer constructor injection when the dependency is required. Lazy lookup hides dependencies and can defer lifetime/cycle failures until runtime.

### Share an object with `IObjectAccessor<T>`

```csharp
var accessor = context.Services.AddObjectAccessor(new StartupState());
accessor.Value.IsConfigured = true;
```

`AddObjectAccessor` inserts the same `ObjectAccessor<T>` instance as singleton registrations for both `ObjectAccessor<T>` and `IObjectAccessor<T>`. It throws if one was already registered; `TryAddObjectAccessor<T>()` returns the existing accessor instead. During configuration, `GetObject<T>()` / `GetObjectOrNull<T>()` retrieves a previously registered accessor value from the service collection.

### Keyed and named services

ABP supports .NET keyed services in conventional registration:

```csharp
[ExposeKeyedService<IInvoiceCalculator>("standard")]
public class StandardInvoiceCalculator : IInvoiceCalculator, ITransientDependency
{
    public decimal Calculate(decimal netAmount) => netAmount;
}

public class CheckoutService
{
    private readonly IInvoiceCalculator _calculator;

    public CheckoutService(
        [FromKeyedServices("standard")] IInvoiceCalculator calculator)
    {
        _calculator = calculator;
    }
}
```

Resolve imperatively with `GetRequiredKeyedService<T>(key)`. A string key is the named-service pattern in this version; there is no separate ABP `INamedServiceProvider` abstraction in the verified dependency-injection sources. If a class has only `[ExposeKeyedService]` and no `[ExposeServices]`, ABP does not add its default unkeyed services.

### Decorating a service (know the limits)

ABP core provides **no** general `Decorate<T>` extension. The descriptor-wrapping pattern below preserves only the original **lifetime value** — it does not preserve the original ABP registration. The inner service is rebuilt with `ActivatorUtilities.CreateInstance`, which bypasses the Autofac/ABP registration pipeline, so that inner instance loses ABP's dynamic-proxy interceptors (validation, unit of work, authorization, auditing, feature checks), convention-based property injection, and `OnActivated` callbacks. It also breaks the shared-instance identity when the type is exposed as both its concrete type and its interface (`ConventionalRegistrarBase` normally redirects those to one instance).

So use this pattern **only** for a simple implementation-type service that does not rely on any of those ABP behaviors. When you need to decorate a service that keeps ABP interception/property injection, use container-specific decoration (Autofac's `RegisterDecorator`) instead:

```csharp
var descriptor = context.Services.LastOrDefault(
    service => service.ServiceType == typeof(IInvoiceCalculator));

if (descriptor?.ImplementationType == null)
{
    throw new InvalidOperationException(
        "IInvoiceCalculator must use an implementation-type registration.");
}

context.Services.Replace(ServiceDescriptor.Describe(
    typeof(IInvoiceCalculator),
    serviceProvider => new LoggingInvoiceCalculator(
        (IInvoiceCalculator)ActivatorUtilities.CreateInstance(
            serviceProvider,
            descriptor.ImplementationType)),
    descriptor.Lifetime));
```

Do not apply this exact pattern to factory, instance, or keyed descriptors; their implementation data lives in different `ServiceDescriptor` properties.

## Validation

- Resolve every intended service type (interface, concrete type, and key) and assert its runtime implementation.
- Inspect `IServiceCollection` after configuration to confirm replacement count and lifetime.
- For singleton/scoped services exposed through multiple types, verify all paths resolve the same instance within the expected scope.
- Verify lazy/cached resolution twice, especially if the underlying service is transient.
- For decoration, test behavior, exception propagation, and preservation of the original lifetime.

## Common Pitfalls

- **Assuming every implemented interface is exposed** — default exposure is name-based. Use `[ExposeServices]` for unrelated interfaces.
- **Forgetting `IncludeSelf`** — explicit exposure can make the concrete class unresolvable.
- **Replacing under the wrong service type** — replace every injection path that consumers actually use.
- **Treating `IAbpLazyServiceProvider` as a fresh resolve each time** — it caches resolved services, including transients.
- **Using service location for required dependencies** — constructor injection makes requirements and cycles visible at startup.
- **Expecting a keyed-only class to resolve unkeyed** — add `[ExposeServices]` explicitly if both forms are required.
- **Decorating a factory/instance descriptor as if it had `ImplementationType`** — branch by descriptor shape or use container-specific decoration.
