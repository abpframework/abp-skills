---
name: propagate-correlation-id
description: "ABP correlation IDs through ASP.NET Core requests and ABP HTTP client proxies. USE FOR: AbpCorrelationIdOptions, UseCorrelationId, ICorrelationIdProvider, X-Correlation-Id propagation between services. DO NOT USE FOR: tracing exporters or OpenTelemetry spans (out of scope); general HTTP security middleware (secure-web-requests); distributed event transport (background-jobs-and-events)."
license: MIT
---

# Propagating Correlation IDs in ABP

## When to Use

- Preserve one request identifier across inbound ASP.NET Core requests and ABP-generated outbound HTTP calls.
- Change the header name or stop echoing the ID in the response.
- Read the current correlation ID in application code.
- Diagnose a missing ID in a service-to-service call made by an ABP HTTP client proxy.

## When Not to Use

- **Distributed traces, spans, exporters, or trace sampling** — out of scope here; ABP ships no OpenTelemetry framework module, so wire the OpenTelemetry .NET SDK directly.
- **General HTTP headers, CSRF, or security middleware** — use secure-web-requests.
- **Distributed event correlation or broker transport** — use background-jobs-and-events.

## How it works

`ICorrelationIdProvider` has two operations: `Get()` returns the current nullable ID, and `Change(string?)` sets it until the returned `IDisposable` is disposed. The default singleton provider stores the value in `AsyncLocal<string?>` and restores the parent value on disposal.

For ASP.NET Core, add the middleware in the request pipeline:

```csharp
public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();
    app.UseCorrelationId();
}
```

`AbpCorrelationIdMiddleware` reads the configured request header. If it is empty, it creates `Guid.NewGuid().ToString("N")` and writes it back to the request headers. It scopes the provider value around the next middleware. By default, it also adds the same ID to the response when the response does not already contain that header.

Configure the two verified options in a module:

```csharp
Configure<AbpCorrelationIdOptions>(options =>
{
    options.HttpHeaderName = "X-Correlation-Id";
    options.SetResponseHeader = true;
});
```

Defaults:

- `HttpHeaderName`: `"X-Correlation-Id"`
- `SetResponseHeader`: `true`

Read or temporarily replace the current value:

```csharp
public class CorrelatedOperation
{
    private readonly ICorrelationIdProvider _correlationIdProvider;

    public CorrelatedOperation(ICorrelationIdProvider correlationIdProvider)
    {
        _correlationIdProvider = correlationIdProvider;
    }

    public async Task RunAsync(string correlationId)
    {
        using (_correlationIdProvider.Change(correlationId))
        {
            await ExecuteAsync();
        }
    }
}
```

ABP HTTP client proxy paths (`ApiDescriptionFinder` and `ClientProxyBase`) call `ICorrelationIdProvider.Get()` and add the configured header when the value is not null. This is the verified service-to-service propagation path; an arbitrary `HttpClient` is not automatically covered by these classes.

## Validation

- Send a request without the configured header and verify the response contains a 32-character `N`-format GUID under that header.
- Send a known header value and verify `ICorrelationIdProvider.Get()` returns it inside the request.
- Call an ABP HTTP client proxy and verify the downstream request carries the same header.
- Set `SetResponseHeader` to `false` and verify the middleware does not add the response header.
- Verify a nested `Change(...)` restores the outer value after disposal.

## Common Pitfalls

- **Omitting `UseCorrelationId()`** — registering the provider alone does not create an inbound request ID.
- **Expecting arbitrary `HttpClient` calls to propagate automatically** — the verified automatic propagation is in ABP HTTP client proxy code; add your own delegating handler for other clients.
- **Forgetting to dispose `Change(...)`** — use a `using` block so the previous `AsyncLocal` value is restored.
- **Using different header names between services** — configure `AbpCorrelationIdOptions.HttpHeaderName` consistently on both ends.
- **Treating a correlation ID as a complete distributed trace** — it is a request identifier, not a replacement for trace/span context.
