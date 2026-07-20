---
name: configure-cors
description: "Configure CORS (browser cross-origin access) for an ABP HTTP API host. USE FOR: the App:CorsOrigins setting (comma-separated, trailing-slash trimming), AddCors + WithOrigins, WithAbpExposedHeaders, SetIsOriginAllowedToAllowWildcardSubdomains for wildcard subdomains, the AllowCredentials vs any-origin conflict, UseCors middleware ordering, and which host/gateway to configure in tiered/microservice solutions. DO NOT USE FOR: OpenIddict client redirect / post-logout URIs (registered on the OpenIddict client application at creation/seeding, not a CORS or auth-config setting); RedirectAllowedUrls and named app URLs (configure-app-urls); CSRF/antiforgery and security response headers (secure-web-requests); calling a remote API from C# (consume-remote-services)."
license: MIT
---

# Configure CORS in ABP

CORS controls which **browser origins** (scheme + host + port) are allowed to call your HTTP API from client-side JavaScript. In ABP you configure it on the **API host** (the `HttpApi.Host` project), using ASP.NET Core's CORS with one ABP-specific helper (`WithAbpExposedHeaders`). The allowed origins come from the `App:CorsOrigins` setting.

This is **not** the same as OpenIddict redirect URIs, `AppUrlOptions`, or `RedirectAllowedUrls` — see *When Not to Use*.

## When to Use

- A browser SPA (Angular/React/Blazor WASM) or another site calls your ABP API and the browser blocks it with a CORS error.
- Adding/removing allowed origins, or supporting wildcard subdomains.
- Getting `UseCors` into the pipeline in the right order.
- Deciding where CORS goes in a tiered or microservice solution (API host vs gateway).

## When Not to Use

- **OpenIddict allowed redirect / post-logout URIs** for the OAuth flow — these are the OpenIddict **client application's** registered URIs (set when the client/application is created or seeded), not a CORS setting. (A login redirect failing is not a CORS problem.)
- **`AppUrlOptions` named app URLs and `RedirectAllowedUrls`** (server-side redirect allow-list) — use the **configure-app-urls** skill.
- **Antiforgery/CSRF and security response headers** (CSP etc.) — use the **secure-web-requests** skill.
- **Calling a remote HTTP API from C#** (no browser, no CORS) — use the **consume-remote-services** skill.

## 1. Allowed origins: `App:CorsOrigins`

The startup templates read allowed origins from the `App:CorsOrigins` setting — a **comma-separated** list of origins (no trailing path), in `appsettings.json`:

```json
{
  "App": {
    "CorsOrigins": "https://*.example.com,http://localhost:4200,https://localhost:44307"
  }
}
```

- Each entry is a full **origin**: scheme + host + optional port. `http://localhost:4200` and `https://localhost:4200` are different origins; so are different ports.
- A leading `*.` in the host (e.g. `https://*.example.com`) marks a **wildcard subdomain** (see step 2).
- The template splits on `,` (removing empty entries) and trims a trailing `/` from each entry (`RemovePostFix("/")`), because a trailing slash makes the origin string not match the browser's `Origin` header.

## 2. The CORS policy

The template's `ConfigureCors` builds a default policy from `App:CorsOrigins`:

```csharp
context.Services.AddCors(options =>
{
    options.AddDefaultPolicy(builder =>
    {
        builder
            .WithOrigins(
                configuration["App:CorsOrigins"]?
                    .Split(",", StringSplitOptions.RemoveEmptyEntries)
                    .Select(o => o.RemovePostFix("/"))
                    .ToArray() ?? Array.Empty<string>())
            .WithAbpExposedHeaders()                     // ABP: exposes ABP's response headers to the browser
            .SetIsOriginAllowedToAllowWildcardSubdomains() // makes https://*.example.com match subdomains
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();                          // only if the browser sends credentials (cookies, HTTP auth, client certs, or fetch credentials: 'include')
    });
});
```

- **`WithAbpExposedHeaders()`** is the only ABP-specific call — it adds ABP's framework response headers, the error-format header (`_AbpErrorFormat`) and the tenant-resolution-error header (`Abp-Tenant-Resolve-Error`), to `Access-Control-Expose-Headers` so browser code can read them. Everything else is plain ASP.NET Core CORS.
- **`SetIsOriginAllowedToAllowWildcardSubdomains()`** is what makes a `https://*.example.com` entry actually match `https://tenant1.example.com`. Without it, the wildcard entry never matches.

## 3. Middleware order — `UseCors`

Add `app.UseCors()` in `OnApplicationInitialization`, **after `UseRouting()` and before `UseAuthentication()`/`UseAuthorization()`**. If it runs too late (after auth) or before routing, preflight requests don't get the CORS headers and the browser blocks the call. The startup template already places it correctly.

## 4. Credentials vs. any origin

`AllowCredentials()` is needed only when the browser sends credentials — cookies, HTTP authentication, client certificates, or `fetch(..., { credentials: 'include' })` (an explicit `Authorization` header alone doesn't require it; that's just an allowed request header). It **cannot** be combined with a wildcard `*` origin — the browser rejects `Access-Control-Allow-Origin: *` together with credentials. That's why the template lists explicit origins (and uses wildcard *subdomains* of a named domain, not `*`). If you don't need credentials, you can loosen origins; if you do, enumerate the exact origins.

## 5. Tiered / microservice solutions

CORS must be configured on **whatever the browser talks to directly**:

- **Layered/tiered app:** the `HttpApi.Host` (and the AuthServer if the SPA hits it directly for the OAuth flow).
- **Microservice solution:** the **API gateway** the SPA calls, plus any service exposed directly to the browser. Individual back-end microservices reached only through the gateway don't need browser CORS.

## Validation

- Reproduce the browser's **preflight**: an `OPTIONS` request to your API with `Origin: <spa-origin>` and `Access-Control-Request-Method: POST` should return `204` with `Access-Control-Allow-Origin: <spa-origin>` (and `Access-Control-Allow-Credentials: true` when credentials are on). Check the actual response headers, not just `appsettings.json`.
- If the origin is missing from the response, the entry doesn't match — check scheme/port and the trailing slash.

## Common Pitfalls

- **Trailing slash** in an origin (`https://example.com/`) — it won't match the browser `Origin` header; drop it (the template's `RemovePostFix("/")` does this for `App:CorsOrigins`).
- **Wildcard subdomain without `SetIsOriginAllowedToAllowWildcardSubdomains()`** — `https://*.example.com` silently never matches.
- **`AllowCredentials()` with a `*` origin** — rejected by the browser; enumerate origins or a named wildcard-subdomain domain.
- **Wrong `UseCors` order** — must be after `UseRouting`, before `UseAuthentication`.
- **Different port/scheme** counts as a different origin — add each SPA dev/prod origin explicitly.
- **Confusing CORS with the OAuth redirect** — a failed login redirect is an OpenIddict client redirect-URI issue (fix the client application's registered redirect URIs, set at client creation/seeding), not CORS.
