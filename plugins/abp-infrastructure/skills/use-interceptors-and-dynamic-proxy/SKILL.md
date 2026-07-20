---
name: use-interceptors-and-dynamic-proxy
description: "ABP cross-cutting behavior via Castle dynamic proxies and IAbpInterceptor. USE FOR: how validation, unit of work, authorization, auditing, feature interceptors are selected; interceptor not running; custom interceptor via Services.OnRegistered. DO NOT USE FOR: module lifecycle (define-application-modules); audit-log persistence (configure-audit-logging); feature values (manage-settings-and-features); services without interception (register-and-replace-services)."
license: MIT
---

# Using Interceptors and Dynamic Proxies

ABP attaches `IAbpInterceptor` implementations while services are registered, then the Autofac/Castle integration creates either an interface proxy or a class proxy. The call must cross that proxy for an interceptor to run.

## When to Use

- Diagnose why validation, `[UnitOfWork]`, `[Authorize]`, `[Audited]`, or `[RequiresFeature]` is not taking effect on a service call.
- Add reusable before/after behavior around application or domain services.
- Select services for interception through `IServiceCollection.OnRegistered`.
- Inspect the invoked method, arguments, target, or return value through `IAbpMethodInvocation`.

## When Not to Use

- **Module lifecycle and ordinary registrations** — use define-application-modules.
- **Audit-log storage, contributors, and entity history** — use configure-audit-logging.
- **Feature definitions and values** — use manage-settings-and-features.
- **Service exposure, replacement, keyed services, or decoration** — use register-and-replace-services.

## How it works

### The invocation contract

Implement `IAbpInterceptor.InterceptAsync(IAbpMethodInvocation)` directly or derive from `AbpInterceptor`. Call `ProceedAsync()` exactly once to continue the chain. The invocation also exposes `Arguments`, `ArgumentsDictionary`, `GenericArguments`, `TargetObject`, `Method`, and `ReturnValue`.

```csharp
using System.Diagnostics;
using Microsoft.Extensions.Logging;
using Volo.Abp.DependencyInjection;
using Volo.Abp.DynamicProxy;

public class ExecutionTimeInterceptor : AbpInterceptor, ITransientDependency
{
    private readonly ILogger<ExecutionTimeInterceptor> _logger;

    public ExecutionTimeInterceptor(ILogger<ExecutionTimeInterceptor> logger)
    {
        _logger = logger;
    }

    public override async Task InterceptAsync(IAbpMethodInvocation invocation)
    {
        var stopwatch = Stopwatch.StartNew();

        try
        {
            await invocation.ProceedAsync();
        }
        finally
        {
            _logger.LogInformation(
                "{MethodName} completed in {ElapsedMilliseconds} ms",
                invocation.Method.Name,
                stopwatch.ElapsedMilliseconds);
        }
    }
}
```

Omitting `ProceedAsync()` intentionally short-circuits the target and all later interceptors. Use `try/finally` when after-logic must run for both success and failure.

### Register a custom interceptor

Choose an explicit marker or attribute. A marker interface keeps the selector simple and avoids intercepting unrelated services.

```csharp
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Collections;
using Volo.Abp.DependencyInjection;

public interface IExecutionTimeEnabled
{
}

public static class ExecutionTimeInterceptorRegistrar
{
    public static void RegisterIfNeeded(IOnServiceRegistredContext context)
    {
        if (typeof(IExecutionTimeEnabled).IsAssignableFrom(context.ImplementationType))
        {
            context.Interceptors.TryAdd<ExecutionTimeInterceptor>();
        }
    }
}

public override void PreConfigureServices(ServiceConfigurationContext context)
{
    context.Services.OnRegistered(ExecutionTimeInterceptorRegistrar.RegisterIfNeeded);
}
```

`ExecutionTimeInterceptor` is conventionally registered because it implements `ITransientDependency`. Register the `OnRegistered` callback early enough to observe the target services; `PreConfigureServices` is the safe module-level location.

### How the built-in interceptors are selected

Each built-in module installs an `OnRegistered` callback. Its registrar tests the implementation type and adds an interceptor only when needed:

| Concern | Registrar trigger |
| --- | --- |
| Validation | Type implements `IValidationEnabled` and is not in `DynamicProxyIgnoreTypes`. |
| Unit of work | `UnitOfWorkHelper.IsUnitOfWorkType(...)` returns true and the type is not ignored. |
| Authorization | Type or any method has `[Authorize]` and the type is not ignored. |
| Auditing | The type is auditable by default, has `[Audited]`, implements `IAuditingEnabled`, or has an audited method, subject to ignore rules. |
| Features | Type or any method has `[RequiresFeature]` and the type is not ignored. |

The registrar decision only attaches the interceptor to the service registration. The interceptor itself performs the runtime check and behavior.

### Hard conditions for interception

All of these must hold:

1. The implementation is registered through ABP DI while the relevant `OnRegistered` callback is active.
2. The service is resolved from DI and invoked through the resolved proxy; `new` bypasses the proxy.
3. The registrar selects the implementation and adds the interceptor type.
4. The call uses an exposed interface, **or** the class-proxy target method is overridable (`virtual`, non-sealed class).
5. Class interception has not been disabled with `DisableAbpClassInterceptors`, a selector, or `DisableAbpFeaturesAttribute.DisableInterceptors`.
6. The Autofac integration is present. `AbpAutofacModule` depends on `AbpCastleCoreModule`; the latter registers the async interceptor adapter.

For an interface proxy, inject and call the interface. For a class proxy, make the intercepted public/protected method `virtual`. A non-virtual class method executes normally but Castle cannot override it.

## Validation

- Resolve the target from an `IServiceScope`; do not instantiate it directly.
- Test both the selected interface path and, if supported, the concrete class path.
- Add a deterministic signal in the custom interceptor and verify it occurs before/after the target once.
- Verify exception behavior: the target exception still propagates and `finally` logic runs.
- For a missing built-in behavior, confirm the module installed its registrar, the type matches the registrar trigger, and the method call crosses a proxy.

## Common Pitfalls

- **A class method is not `virtual`** — class proxies cannot intercept it. Inject an exposed interface or make the method overridable.
- **The object was created with `new`** — only the container-resolved proxy carries interceptors.
- **The service was registered before the callback** — register selector callbacks in `PreConfigureServices`.
- **The selector checks the service interface instead of `ImplementationType`** — `IOnServiceRegistredContext.ImplementationType` is what built-in registrars inspect.
- **`ProceedAsync()` is called zero or multiple times** — zero short-circuits execution; multiple calls execute the downstream chain repeatedly.
- **The type is deliberately ignored** — check `DynamicProxyIgnoreTypes`, `DisableAbpClassInterceptors`, and `DisableAbpFeaturesAttribute` before changing business code.
