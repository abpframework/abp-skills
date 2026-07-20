---
name: configure-app-urls
description: "Named application roots and external URLs with AppUrlOptions, resolved tenant-aware via IAppUrlProvider. USE FOR: AppUrlOptions.Applications; RootUrl and named Urls; email links; cross-application links; tenantId and tenantName placeholders; redirect allow-list checks. DO NOT USE FOR: rendering the email body (render-text-templates) or sending it (send-emails); remote service base addresses (consume-remote-services); resolving tenants by domain (configure-multi-tenancy)."
license: MIT
---

# Configure Application URLs in ABP

These APIs are in the `Volo.Abp.UI.Navigation` package and the `Volo.Abp.UI.Navigation.Urls` namespace. `AppUrlProvider` uses HTTP URL helpers internally, but `IAppUrlProvider` and `AppUrlOptions` are not declared in `Volo.Abp.Http`.

## When to Use

- Generate absolute links for password reset, email confirmation, invitations, or other email content.
- Link from one application to another without hard-coding deployment hosts.
- Resolve tenant placeholders against the current tenant.
- Normalize a configured external URL or check a redirect target against configured allowed URLs.

## When Not to Use

- **Render the email body** — use render-text-templates; **send it** — use send-emails (after resolving the link).
- **Configure remote service endpoints or make outbound HTTP calls** — use consume-remote-services, which owns `AbpRemoteServiceOptions.BaseUrl`.
- **Resolve the current tenant from a host name** — use configure-multi-tenancy.

## How it works

### Configure application roots and named paths

`AppUrlOptions.Applications` is an `ApplicationUrlDictionary`. Indexing a new application name creates an `ApplicationUrlInfo` with a nullable `RootUrl` and an initially empty `IDictionary<string, string>` named `Urls`.

```csharp
using Volo.Abp.UI.Navigation.Urls;

Configure<AppUrlOptions>(options =>
{
    options.Applications["MVC"].RootUrl = "https://{{tenantName}}.example.com";
    options.Applications["MVC"].Urls["PasswordReset"] = "account/reset-password";

    options.Applications["Admin"].RootUrl = "https://admin.example.com";
});
```

When a root is present, the provider calls `EnsureEndsWith('/')` on it and then concatenates the named value. Store named values as relative paths without a leading slash.

### Resolve links through IAppUrlProvider

`GetUrlAsync(appName, urlName)` returns the configured root or named URL after multi-tenant placeholder replacement. It throws `AbpException` when the configured lookup returns null or empty. `GetUrlOrNullAsync` exposes the raw configured lookup behavior without that final required-value check.

```csharp
public class PasswordResetLinkFactory : ITransientDependency
{
    private readonly IAppUrlProvider _appUrlProvider;

    public PasswordResetLinkFactory(IAppUrlProvider appUrlProvider)
    {
        _appUrlProvider = appUrlProvider;
    }

    public async Task<string> CreateAsync(string userId, string token)
    {
        var baseUrl = await _appUrlProvider.GetUrlAsync("MVC", "PasswordReset");

        return $"{baseUrl}?userId={Uri.EscapeDataString(userId)}&token={Uri.EscapeDataString(token)}";
    }
}
```

Resolve the URL before passing it into a template model. Encode every query value; `IAppUrlProvider` does not build query strings.

### Use tenant placeholders

The default `IMultiTenantUrlProvider` recognizes:

- `{{tenantId}}`
- `{{tenantName}}`
- the legacy `{0}` placeholder

For a tenant, the resolved value includes a trailing dot. For the host side, the placeholder and an adjacent dot are removed. The provider can load the tenant name from `ITenantStore` when the current tenant has an ID but no name.

### Configure redirect allow-list entries separately

`RedirectAllowedUrls` is independent from `Applications`:

```csharp
Configure<AppUrlOptions>(options =>
{
    options.RedirectAllowedUrls.Add("https://{{tenantName}}.example.com");
    options.RedirectAllowedUrls.Add("https://*.apps.example.com");
});
```

Use `NormalizeUrlAsync` to apply tenant placeholder replacement to an arbitrary configured URL. Use `IsRedirectAllowedUrlAsync` when validating redirect targets; it normalizes each configured allow-list entry before comparing it.

## Validation

- Resolve each root and named URL for the host and for a current tenant.
- Assert that missing application configuration follows the intended `GetUrlAsync` or `GetUrlOrNullAsync` path.
- Generate a complete email link and verify query values are encoded exactly once.
- Test allowed and rejected redirect targets, including tenant and wildcard-subdomain entries.
- Confirm configuration is present in every deployed application that generates links.

## Common Pitfalls

- **Using the wrong package or namespace** — the APIs live in `Volo.Abp.UI.Navigation.Urls`.
- **Hard-coding hosts in email templates** — resolve a named URL and pass the result into the template model.
- **Expecting `IAppUrlProvider` to append query parameters** — it only resolves configured URLs.
- **Passing an unencoded token in a query string** — encode each value at the link-construction boundary.
- **Treating `GetUrlOrNullAsync` as configuration validation** — with a configured root, its named-URL lookup joins the root with the dictionary result; explicitly test every required name.
- **Confusing application URLs with redirect allow-list entries** — configure `RedirectAllowedUrls` separately.
