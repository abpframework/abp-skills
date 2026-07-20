---
name: use-cancellation-tokens
description: "Cooperative cancellation across ABP services/repositories/UOW via ICancellationTokenProvider. USE FOR: ICancellationTokenProvider.Token and Use; NullCancellationTokenProvider; HttpContextCancellationTokenProvider and RequestAborted; FallbackToProvider precedence; passing CancellationToken through methods. DO NOT USE FOR: background job retry (background-jobs-and-events); generic async performance (out of scope); HTTP auth (configure-openiddict-authentication)."
license: MIT
---

# Use Cancellation Tokens in ABP

Prefer an explicit `CancellationToken` parameter at public async boundaries and pass it through every cancellable call. Use `ICancellationTokenProvider` when ABP ambient cancellation must reach code that does not receive a token directly.

## When to Use

- Propagate an incoming token through application services, repositories, EF Core, MongoDB, HTTP calls, and stream operations.
- Use the current ASP.NET Core request's `HttpContext.RequestAborted` token indirectly.
- Add cancellation to custom code that is called through ABP infrastructure without an explicit token.
- Temporarily override the ambient token for a scoped operation or test.

## When Not to Use

- **Configure background job workers, retries, or event processing** — use background-jobs-and-events.
- **Treat cancellation as an async performance fix** — cancellation is cooperative control flow, not parallelism.
- **Configure HTTP authentication** — use configure-openiddict-authentication.

## How it works

### Pass explicit tokens through service boundaries

```csharp
public class ProductAppService : ApplicationService
{
    private readonly IRepository<Product, Guid> _productRepository;
    private readonly IExternalCatalog _externalCatalog;

    public ProductAppService(
        IRepository<Product, Guid> productRepository,
        IExternalCatalog externalCatalog)
    {
        _productRepository = productRepository;
        _externalCatalog = externalCatalog;
    }

    public async Task RefreshAsync(
        Guid productId,
        CancellationToken cancellationToken = default)
    {
        var product = await _productRepository.GetAsync(
            productId,
            cancellationToken: cancellationToken);

        var details = await _externalCatalog.GetAsync(
            product.ExternalId,
            cancellationToken);

        product.Update(details);

        await _productRepository.UpdateAsync(
            product,
            cancellationToken: cancellationToken);
    }
}
```

Do not replace a received token with `CancellationToken.None`, and do not stop propagation at a repository or external API call.

### Use the ambient provider when no parameter is available

`ICancellationTokenProvider` exposes:

```csharp
CancellationToken Token { get; }
IDisposable Use(CancellationToken cancellationToken);
```

```csharp
public class CatalogImporter : ITransientDependency
{
    private readonly ICancellationTokenProvider _cancellationTokenProvider;

    public CatalogImporter(ICancellationTokenProvider cancellationTokenProvider)
    {
        _cancellationTokenProvider = cancellationTokenProvider;
    }

    public async Task ImportAsync()
    {
        var token = _cancellationTokenProvider.Token;
        token.ThrowIfCancellationRequested();
        await ImportCoreAsync(token);
    }
}
```

Read the provider token near the operation and pass that captured token through the call chain.

### Understand the built-in providers

- `AbpThreadingModule` registers the singleton `NullCancellationTokenProvider.Instance`. Its token is `CancellationToken.None` unless an ambient override is active.
- In ASP.NET Core, `HttpContextCancellationTokenProvider` replaces that service. It returns the override token first, otherwise `HttpContext.RequestAborted`, otherwise `CancellationToken.None` when no HTTP context exists.

ABP repository bases expose `GetCancellationToken(preferredValue)`, which calls `FallbackToProvider`. A supplied cancellable token wins; `default` and `CancellationToken.None` fall back to the provider token. EF Core and MongoDB unit-of-work infrastructure use the same pattern.

### Override cancellation only for a scope

`Use` stores an ambient override and returns a scope that must be disposed:

```csharp
using (_cancellationTokenProvider.Use(cancellationToken))
{
    await RunPipelineAsync();
}
```

The override flows through the ambient async context. Keep the scope as narrow as possible and never forget `using`.

## Validation

- Pass an already-canceled token and assert the first cancellable operation observes it.
- In an ASP.NET Core integration test, abort the request and verify downstream work receives `RequestAborted`.
- Test code outside an HTTP request and confirm the fallback is `CancellationToken.None` unless explicitly overridden.
- Verify `Use` restores the previous token after disposal, including nested async calls.
- Inspect every awaited database, HTTP, stream, and delay call in the target flow for token propagation.

## Common Pitfalls

- **Accepting a token but not forwarding it** — cancellation remains cooperative and only works where the token is observed.
- **Assuming every environment has an HTTP request token** — non-web and out-of-request code falls back to `CancellationToken.None`.
- **Passing `CancellationToken.None` expecting to suppress ambient cancellation** — `FallbackToProvider` treats it like `default` and uses the provider token.
- **Calling `Use` without disposing the returned scope** — the override can leak into later work in the same ambient context.
- **Swallowing `OperationCanceledException` as a normal failure** — preserve cancellation semantics unless the boundary explicitly translates them.
- **Creating a new `CancellationTokenSource` without linking the caller token** — it disconnects the operation from upstream cancellation.
