---
name: secure-web-requests
description: "ABP ASP.NET Core CSRF protection and response security headers. USE FOR: AbpAntiForgeryOptions and antiforgery cookies; MVC antiforgery validation; IAbpAntiForgeryManager; Blazor/WebAssembly antiforgery; AbpSecurityHeadersOptions; UseAbpSecurityHeaders; CSP and script nonces. DO NOT USE FOR: token issuance/API auth (configure-openiddict-authentication); permissions (permissions-and-authorization); MVC/Razor pages (mvc-razor-ui); Blazor components (blazor-ui)."
license: MIT
---

# Securing Web Requests

ABP's web-request security has two separate paths: MVC antiforgery services/filters validate state-changing browser requests, while `AbpSecurityHeadersMiddleware` adds response headers and optional Content Security Policy (CSP). Configure and validate both independently.

## When to Use

- Configure CSRF token cookie generation and MVC automatic validation.
- Issue an antiforgery token cookie for a JavaScript or Blazor client.
- Wire antiforgery middleware in a Blazor host.
- Add baseline browser security headers, custom headers, CSP, or script nonces.
- Exclude a known endpoint/path from ABP security-header processing after reviewing the risk.

## When Not to Use

- **OpenIddict/API authentication** — use configure-openiddict-authentication.
- **Permissions, policies, and resource authorization** — use permissions-and-authorization.
- **Build MVC/Razor UI pages** — use mvc-razor-ui.
- **Build Blazor components** — use blazor-ui.

## How it works

### MVC antiforgery is registered by the MVC module

`AbpAspNetCoreMvcModule` adds `AbpAutoValidateAntiforgeryTokenAttribute` to MVC's global filters. The filter calls ASP.NET Core `IAntiforgery.ValidateRequestAsync` when validation is required and returns `AntiforgeryValidationFailedResult` on validation failure.

Configure ABP-specific behavior in the host module:

```csharp
using Volo.Abp.AspNetCore.Mvc.AntiForgery;

Configure<AbpAntiForgeryOptions>(options =>
{
    options.AutoValidate = true;
    options.AutoValidateFilter = controllerType =>
        controllerType.Namespace?.StartsWith("MyCompany.MyProduct") == true;
});
```

Defaults:

- `AutoValidate = true`.
- `AutoValidateFilter` returns true for every controller type.
- Ignored HTTP methods are `GET`, `HEAD`, `TRACE`, and `OPTIONS`.
- `TokenCookie.Name = "XSRF-TOKEN"`, `HttpOnly = false`, `IsEssential = true`, `SameSite = None`, expiration 3650 days.
- `AuthCookieSchemaName = "Identity.Application"`.
- `NormalizeUserIdClaimIssuer = true` (this option and the `AbpAntiforgery` wrapper described below are **ABP 10.6+**; 10.5 has neither).

Changing the ignored-method set changes which verbs the automatic filter validates. Do not add a state-changing verb to it.

### When automatic validation runs

After the global auto-validation switches and method filter pass, the base ABP filter applies these request rules:

1. If the configured authentication cookie is present, validate.
2. Otherwise, if the antiforgery cookie name is known but that cookie is absent, skip validation as a non-browser request.
3. Otherwise, require a token.

This behavior is cookie/request-based; it is not a replacement for authentication or authorization.

### Generate a token cookie

`IAbpAntiForgeryManager` exposes `SetCookie()` and `GenerateToken()`:

```csharp
public class AntiforgeryTokenController : AbpController
{
    private readonly IAbpAntiForgeryManager _antiforgeryManager;

    public AntiforgeryTokenController(
        IAbpAntiForgeryManager antiforgeryManager)
    {
        _antiforgeryManager = antiforgeryManager;
    }

    [HttpGet]
    public void SetCookie()
    {
        _antiforgeryManager.SetCookie();
    }
}
```

`SetCookie()` calls `GenerateToken()`, then appends the configured token cookie. `GenerateToken()` returns the request token from `IAntiforgery.GetAndStoreTokens`.

ABP wraps an implementation-type `IAntiforgery` registration with `AbpAntiforgery` so token generation and validation use ABP's claim normalization. A custom factory/instance registration is left unchanged by that wrapping code.

### Blazor host and WebAssembly client wiring

ABP Blazor templates place ASP.NET Core's antiforgery middleware after routing/authentication-related middleware and before endpoint mapping:

```csharp
app.UseRouting();
app.UseAuthentication();
app.UseAntiforgery();
app.UseAuthorization();
app.UseConfiguredEndpoints();
```

The simpler hosted WebAssembly template uses `UseRouting()`, then `UseAntiforgery()`, then maps Razor components.

`AbpBlazorClientHttpMessageHandler` reads `XSRF-TOKEN` and sends it as `RequestVerificationToken` only for same-host-and-port requests whose method is not GET/HEAD/TRACE/OPTIONS. If a custom client bypasses that handler, it must provide equivalent token transport.

### Add ABP security headers

The middleware is opt-in:

```csharp
using Volo.Abp.AspNetCore.Security;

Configure<AbpSecurityHeadersOptions>(options =>
{
    options.Headers["Referrer-Policy"] = "strict-origin-when-cross-origin";
    options.UseContentSecurityPolicyHeader = true;
    options.ContentSecurityPolicyValue =
        "default-src 'self'; object-src 'none'; form-action 'self'; frame-ancestors 'none'";
});

public override void OnApplicationInitialization(
    ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();

    app.UseRouting();
    app.UseAbpSecurityHeaders();
    app.UseConfiguredEndpoints();
}
```

Place it after routing so `HttpContext.GetEndpoint()` and endpoint metadata are available, and before endpoint execution.

Unless the request is excluded, the middleware always adds if absent:

- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `X-Frame-Options: SAMEORIGIN`

Entries in `AbpSecurityHeadersOptions.Headers` are then added; for those custom entries, an existing response value is overwritten.

### CSP and script nonces

`UseContentSecurityPolicyHeader` and `UseContentSecurityPolicyScriptNonce` default to false. When CSP is enabled, the middleware handles a request only as CSP-capable HTML when its `Accept` includes `text/html`, `*/*`, or `application/xhtml+xml` and endpoint metadata exists. It writes CSP on response start only for a 2xx response whose content type starts with `text/html`, and it does not overwrite an existing CSP header.

If `ContentSecurityPolicyValue` is empty, the fallback is:

```text
object-src 'none'; form-action 'self'; frame-ancestors 'none'
```

With script nonces enabled, the middleware creates a per-request nonce. MVC/Razor views can render it with:

```html
<script @Html.GetScriptNonceAttribute() src="/js/app.js"></script>
```

If the configured CSP has no `script-src`, ABP appends one containing the nonce. If it has `script-src`, ABP appends the nonce to that directive.

### Exclusions

`[IgnoreAbpSecurityHeader]` on a controller/action endpoint skips this middleware entirely. `IgnoredScriptNoncePaths` and any `IgnoredScriptNonceSelectors` that return true also cause an early return, so they skip all three baseline headers and custom headers as well as CSP/nonce processing.

```csharp
Configure<AbpSecurityHeadersOptions>(options =>
{
    options.IgnoredScriptNoncePaths.Add("/external-callback");
});
```

Despite their names, these option lists are full middleware exclusions. Keep them narrow. The OpenID Connect module adds `/signout-oidc` to `IgnoredScriptNoncePaths`.

## Validation

- Send an unsafe cookie-authenticated MVC request without a token and verify antiforgery validation fails; repeat with the issued cookie/header token and verify success.
- Confirm safe ignored verbs remain readable without a token and no state-changing verb is ignored.
- For Blazor WebAssembly, inspect a same-origin unsafe request and verify `RequestVerificationToken` matches `XSRF-TOKEN`.
- Request a routed endpoint through `UseAbpSecurityHeaders` and assert the three baseline headers plus configured custom headers.
- For CSP, verify a successful HTML response contains the policy and each nonce-bearing script uses the generated nonce; verify non-HTML/non-2xx behavior separately.
- Test every exclusion path/attribute and document why skipping all security headers is acceptable there.

## Common Pitfalls

- **Disabling `AutoValidate` globally to fix one client** — this removes MVC automatic CSRF validation. Fix token issuance/transport or narrowly filter the intended controller.
- **Treating bearer authentication as CSRF protection for cookie-authenticated browser calls** — the ABP filter explicitly validates when the auth cookie is present.
- **Forgetting `UseAntiforgery()` in a Blazor host** — follow the verified template order before mapped Razor-component endpoints.
- **Calling `UseAbpSecurityHeaders()` before routing** — endpoint metadata and CSP handling depend on a selected endpoint.
- **Enabling a nonce without applying it to scripts** — render `GetScriptNonceAttribute()` on allowed script tags.
- **Assuming `IgnoredScriptNoncePaths` disables only nonces** — it bypasses the entire middleware for the matching request.
- **Expecting CSP to overwrite a header already set downstream** — ABP keeps an existing `Content-Security-Policy` value.
