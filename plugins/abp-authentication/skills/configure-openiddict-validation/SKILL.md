---
name: configure-openiddict-validation
description: >
  Configure the ABP OpenIddict validation (resource-server / API token-validation) side — how an API host validates incoming access tokens, distinct from the auth server that issues them.
  USE FOR: PreConfigure the OpenIddict builder then .AddValidation(...), or PreConfigure the OpenIddictValidationBuilder, options.AddAudiences, options.UseLocalServer (same-process auth server) vs a remote issuer (options.SetIssuer / AddAbpJwtBearer Authority+Audience), options.UseAspNetCore, ForwardIdentityAuthenticationForBearer, app.UseAbpOpenIddictValidation, introspection (UseIntrospection / SetClientId / SetClientSecret), EnableTokenEntryValidation.
  DO NOT USE FOR: issuing tokens / configuring the OpenIddict server, token lifetimes, signing/encryption certificates — use configure-openiddict-authentication; refreshing role/profile/custom claims mid-session — use configure-dynamic-claims; Swagger OAuth wiring — use configure-swagger-openapi.
license: MIT
---

# Configure OpenIddict Validation in ABP

The **validation** side is the resource server: the API host that receives an
`access_token` on each request, verifies it, and turns it into a
`ClaimsPrincipal`. This is a separate concern from the OpenIddict **server**
that issues the tokens (see the **configure-openiddict-authentication** skill).

ABP wires validation through OpenIddict's `OpenIddictValidationBuilder`, whose
documented extension methods include `AddAudiences()` (for resource servers),
`SetIssuer()`, `UseIntrospection()`, `SetClientId()` / `SetClientSecret()`,
`EnableAuthorizationEntryValidation()`, `EnableTokenEntryValidation()`,
`UseLocalServer()`, and `UseAspNetCore()`.

## When to Use

- Setting the expected audience for tokens this API accepts (`AddAudiences`).
- Choosing how the API validates tokens: same-process (`UseLocalServer`) vs a
  remote authority.
- Forwarding cookie-authenticated apps to bearer validation for API calls
  (`ForwardIdentityAuthenticationForBearer`).
- Placing `app.UseAbpOpenIddictValidation()` in the request pipeline.
- Reference tokens / introspection against a remote server.

## When Not to Use

- **Issuing tokens, flows, token lifetimes, signing/encryption certificates** —
  that is the server side: use **configure-openiddict-authentication**.
- **Refreshing roles/claims mid-session without re-login** — use
  **configure-dynamic-claims**.
- **Swagger OAuth UI wiring** — use **configure-swagger-openapi**.

## Where configuration goes

Builder configuration goes in `PreConfigureServices`. Two equivalent entry points:

```csharp
// via the top-level OpenIddictBuilder
PreConfigure<OpenIddictBuilder>(builder =>
{
    builder.AddValidation(options =>
    {
        options.AddAudiences("MyProjectName");
        options.UseLocalServer();
        options.UseAspNetCore();
    });
});

// or directly on the validation builder
PreConfigure<OpenIddictValidationBuilder>(options =>
{
    // same options...
});
```

`AddValidation()` registers the OpenIddict token-validation services (docs:
*OpenIddictBuilder* → `AddValidation()` → contains `OpenIddictValidationBuilder`
configurations).

## Local (same-process auth server)

Use this when the API host **is** the auth server, or runs in the same process as
the OpenIddict server registration (the non-tiered app templates — `HttpApi.Host`,
`Web`, `Blazor.Server` — do exactly this). `UseLocalServer()` registers the
validation/server integration so validation reads the in-process server's
keys/config directly — no network call to a discovery endpoint. The snippet under
*Where configuration goes* above is this exact local pattern.

## Remote authority (API is a separate resource server)

When the API is a standalone resource server pointing at a **remote** auth server,
there are two ABP-supported patterns:

### Option A — `AddAbpJwtBearer` (JWT bearer against a remote authority)

This is what the OpenIddict module's standalone API demo does — a separate API
project depending on `AbpAspNetCoreAuthenticationJwtBearerModule`:

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddAbpJwtBearer(options =>
    {
        options.Authority = "https://localhost:44301"; // the remote auth server
        options.Audience  = "MyProjectNameResource";
    });
```

`Authority` points at the remote OpenIddict server; the middleware fetches its
discovery document / signing keys and validates JWTs against them. `AddAbpJwtBearer`
is the ABP wrapper over ASP.NET Core's `AddJwtBearer`.

### Option B — `OpenIddictValidationBuilder` against a remote issuer

Using the validation builder with `SetIssuer()` so it discovers the remote
server's configuration, optionally switching to `UseIntrospection()` for reference
tokens:

```csharp
var configuration = context.Services.GetConfiguration();
PreConfigure<OpenIddictValidationBuilder>(options =>
{
    options.SetIssuer("https://localhost:44301");
    options.AddAudiences("MyProjectNameResource");

    // introspection (needed for reference/opaque tokens):
    options.UseIntrospection();
    options.SetClientId("MyProjectNameResource");
    // Read the client secret from a secret-backed provider, never a literal
    options.SetClientSecret(configuration["AuthServer:ClientSecret"]);

    options.UseSystemNetHttp(); // ⚠️ see note below
    options.UseAspNetCore();
});
```

- `SetIssuer()` — docs: sets the URI used to locate the OAuth 2.0 / OIDC
  configuration document via provider discovery.
- `UseIntrospection()` — docs: use introspection instead of local/direct
  validation.
- `SetClientId()` / `SetClientSecret()` — docs: credentials used when talking to
  the remote authorization server (e.g. for introspection).
- **`UseSystemNetHttp()` is an OpenIddict-native method** — add the
  `OpenIddict.Validation.SystemNetHttp` package to use it; it's **not an ABP wrapper**. It
  registers the `System.Net.Http` client OpenIddict uses to call the remote
  discovery / introspection endpoints, so it's needed for **remote** validation
  (remote OIDC discovery or introspection). Use `UseLocalServer()` when the auth server
  is in the **same process**; a **remote** API validates against the issuer instead —
  with `AddAbpJwtBearer` (Authority + Audience) or OpenIddict's remote validation. See the
  OpenIddict docs: <https://documentation.openiddict.com>

## Forwarding cookie auth to bearer, and the pipeline middleware

In UI hosts that also serve APIs (cookie login **and** bearer API calls),
`ForwardIdentityAuthenticationForBearer` sends requests carrying an
`Authorization: Bearer ...` header to the validation scheme instead of the cookie
scheme:

```csharp
private void ConfigureAuthentication(ServiceConfigurationContext context)
{
    context.Services.ForwardIdentityAuthenticationForBearer(
        OpenIddictValidationAspNetCoreDefaults.AuthenticationScheme);
}
```

`ForwardIdentityAuthenticationForBearer(jwtBearerScheme = "Bearer")` (ABP Identity
extension) sets the application cookie's `ForwardDefaultSelector` to route bearer
requests to the given scheme.

In `OnApplicationInitialization`, add `app.UseAbpOpenIddictValidation()` **after**
`app.UseAuthentication()` (as the templates do):

```csharp
app.UseAuthentication();
app.UseAbpOpenIddictValidation();
// ...
app.UseAuthorization();
```

`UseAbpOpenIddictValidation(schema = OpenIddictValidationAspNetCoreDefaults.AuthenticationScheme)`
(ABP middleware) authenticates against the validation scheme and assigns the
resulting principal to `HttpContext.User` when the request is not already
authenticated.

## Extra validation options

- `EnableTokenEntryValidation()` — docs: checks the token entry in the database on
  each request, giving **immediate revocation** at the cost of a DB hit per call. Use it
  when the API validates locally against the same database; an external API that can't
  reach the server's database should use **introspection** instead. It is not a blanket
  requirement just because the server issues reference tokens.
- `EnableAuthorizationEntryValidation()` — docs: same idea for the authorization
  entry. Both only work with an OpenIddict-based server and add a DB hit per
  request (performance cost).

## Validation

- Build the API host module; a clean compile confirms the wiring.
- Local: call an authorized endpoint with an access token from the in-process
  server — 200 confirms `UseLocalServer` + `AddAudiences` accept it; a wrong
  audience should 401.
- Remote: point `Authority`/`SetIssuer` at the auth server and confirm the API
  reaches its discovery endpoint and validates a token issued by that server.
- Bearer forwarding: in a UI host, confirm a cookie request renders the page while
  the same endpoint with `Authorization: Bearer <token>` is validated as an API call.

## Common Pitfalls

- Mixing up the two sides: lifetimes, flows, certificates are **server-side**
  (configure-openiddict-authentication); this skill only covers how the resource
  server **validates** incoming tokens.
- `AddAudiences` must match the token's audience — a mismatch yields 401 even with
  a valid signature.
- `UseLocalServer` only works when the server lives in the same process; a
  standalone API must use a remote pattern (`AddAbpJwtBearer` or `SetIssuer`).
- Order: `app.UseAbpOpenIddictValidation()` goes after `app.UseAuthentication()`
  and before `app.UseAuthorization()`.
- `EnableTokenEntryValidation` / `EnableAuthorizationEntryValidation` add a DB
  query per request — enable only when you need immediate revocation, not just
  because the server issues reference tokens.
- `UseSystemNetHttp()` is OpenIddict-native (the `OpenIddict.Validation.SystemNetHttp`
  package), not an ABP wrapper — see the OpenIddict docs for its options.

## References

- `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/modules/openiddict.md` (OpenIddictValidationBuilder options)
- `https://github.com/abpframework/abp/blob/rel-10.5/modules/openiddict/src/Volo.Abp.OpenIddict.AspNetCore/Microsoft/AspNetCore/Builder/ApplicationBuilderAbpOpenIddictMiddlewareExtension.cs` (`UseAbpOpenIddictValidation`)
- `https://github.com/abpframework/abp/blob/rel-10.5/modules/identity/src/Volo.Abp.Identity.AspNetCore/Microsoft/AspNetCore/Extensions/DependencyInjection/AbpAspNetCoreServiceCollectionExtensions.cs` (`ForwardIdentityAuthenticationForBearer`)
- `https://github.com/abpframework/abp/blob/rel-10.5/templates/app/aspnet-core/src/MyCompanyName.MyProjectName.HttpApi.HostWithIds/MyProjectNameHttpApiHostModule.cs` (`AddValidation` + `UseLocalServer` + `UseAspNetCore`)
- `https://github.com/abpframework/abp/blob/rel-10.5/modules/openiddict/app/OpenIddict.Demo.API/Program.cs` (`AddAbpJwtBearer` remote authority)
- OpenIddict docs: <https://documentation.openiddict.com>
