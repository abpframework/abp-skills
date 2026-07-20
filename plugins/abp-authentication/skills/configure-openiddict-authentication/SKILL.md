---
name: configure-openiddict-authentication
description: >
  Configure the ABP OpenIddict auth server — token lifetimes, refresh tokens, PKCE, disabling the HTTPS requirement in dev, and production signing/encryption certificates.
  USE FOR: OpenIddictServerBuilder / AbpOpenIddictAspNetCoreOptions setup, SetAccessTokenLifetime/SetRefreshTokenLifetime, enabling refresh_token + offline_access, DisableTransportSecurityRequirement, AddProductionEncryptionAndSigningCertificate, access-token encryption, TokenCleanupOptions.
  DO NOT USE FOR: defining/checking app permissions — use the permissions-and-authorization skill; per-entity resource access — use the authorize-resources skill; refreshing role/profile/custom claims mid-session without re-login — use the configure-dynamic-claims skill.
license: MIT
---

# Configure OpenIddict Authentication in ABP

ABP's OpenIddict module wraps [OpenIddict](https://github.com/openiddict/openiddict-core) to provide the OAuth 2.0 / OpenID Connect auth server (single sign-on, single log-out, API access control). Applications, scopes, authorizations and tokens are persisted to the database.

`AbpOpenIddictAspNetCoreModule` registers the server for you: it calls `services.AddOpenIddict().AddServer(...)`, enables the standard flows (authorization code, hybrid, implicit, password, client credentials, refresh token, device, none, token exchange), registers the standard scopes (`openid`, `email`, `profile`, `phone`, `roles`, `address`, `offline_access`), and enables ASP.NET Core pass-through for the `connect/*` endpoints. You customize it through `PreConfigure<...>` and `Configure<...>`.

The framework *enabling* a flow doesn't mean a new client should *use* it: for new clients prefer **authorization code + PKCE** (web / SPA / mobile) or **client credentials** (server-to-server), and treat **implicit** and **password** (ROPC) as legacy — enable them only for existing clients that still require them.

## When to Use

- Adjusting token lifetimes (authorization code, access, identity, refresh).
- Enabling refresh tokens (`refresh_token` grant + `offline_access` scope).
- Configuring PKCE.
- Allowing HTTP locally by disabling the transport-security requirement in development.
- Registering production signing/encryption certificates.
- Toggling access-token encryption, claim destinations, or the token-cleanup background job.

## When Not to Use

- **Defining or checking application permissions** — use the **permissions-and-authorization** skill instead.
- **Access that depends on a specific entity instance** — use the **authorize-resources** skill.
- **Refreshing roles, profile, or custom claims mid-session without re-login** — use the **configure-dynamic-claims** skill (note: permissions are *not* in the default dynamic-claims set).
- **Defining or checking permission grants** — use the **permissions-and-authorization** skill; permission checks read the current grant, they are not refreshed through the dynamic-claims pipeline.

## Where configuration goes

Builder configuration (`OpenIddictServerBuilder`, `OpenIddictValidationBuilder`, `AbpOpenIddictAspNetCoreOptions`) goes in `PreConfigureServices`. `TokenCleanupOptions` and runtime options like `OpenIddictServerAspNetCoreOptions` go in `ConfigureServices`. Put this in your `AuthServerModule` (or `HttpApiHostModule` if you don't have a separate auth server).

```csharp
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    PreConfigure<OpenIddictServerBuilder>(builder =>
    {
        // server-side configuration
    });
}
```

## Token lifetimes

Configure lifetimes on the `OpenIddictServerBuilder`:

```csharp
PreConfigure<OpenIddictServerBuilder>(builder =>
{
    builder.SetAuthorizationCodeLifetime(TimeSpan.FromMinutes(30));
    builder.SetAccessTokenLifetime(TimeSpan.FromMinutes(30));
    builder.SetIdentityTokenLifetime(TimeSpan.FromMinutes(30));
    builder.SetRefreshTokenLifetime(TimeSpan.FromDays(14));
});
```

## Refresh tokens

Two things are required:

1. The client application must be granted the `refresh_token` grant type. In the `OpenIddictDataSeedContributor`, add `OpenIddictConstants.GrantTypes.RefreshToken` to the `grantTypes` list in the `CreateApplicationAsync` call. If the database is already seeded, re-create the client.
2. The client must request the `offline_access` scope:
   - Razor/MVC and Blazor Server: `options.Scope.Add("offline_access");` in the OpenIdConnect options.
   - Blazor WASM: `options.ProviderOptions.DefaultScopes.Add("offline_access");` in `AddOidcAuthentication`.
   - Angular: add `offline_access` to the `oAuthConfig` scopes in `environment.ts` (already configured in the template).

Keep the cookie `ExpireTimeSpan` roughly aligned with the refresh token lifetime. If the cookie outlives the refresh token, the user still appears signed in locally (the cookie session stays valid) but can no longer silently obtain a fresh `access_token` once the refresh token expires — so their API calls start failing. Aligning the two makes the local session and token refresh expire together; it does not make an expired token valid.

## PKCE

PKCE is standard OpenIddict configuration. See the OpenIddict docs: <https://documentation.openiddict.com/configuration/proof-key-for-code-exchange.html>

## Disabling the HTTPS (transport security) requirement in development

By default OpenIddict requires HTTPS on all endpoints. To allow HTTP locally, configure `OpenIddictServerAspNetCoreOptions` in `ConfigureServices` (only do this in development):

```csharp
Configure<OpenIddictServerAspNetCoreOptions>(options =>
{
    options.DisableTransportSecurityRequirement = true;
});
```

## Development vs. production certificates

`AbpOpenIddictAspNetCoreOptions.AddDevelopmentEncryptionAndSigningCertificate` defaults to `true`. When it is on, the module calls `builder.AddDevelopmentEncryptionCertificate()` and `builder.AddDevelopmentSigningCertificate()` — user-specific certificates suitable for **development only**.

For non-development environments you must turn this off and register your own certificates:

```csharp
PreConfigure<AbpOpenIddictAspNetCoreOptions>(options =>
{
    options.AddDevelopmentEncryptionAndSigningCertificate = false;
});

var configuration = context.Services.GetConfiguration();
PreConfigure<OpenIddictServerBuilder>(builder =>
{
    // Read the certificate path/password from configuration or a secret store — don't hardcode the password
    builder.AddProductionEncryptionAndSigningCertificate(
        configuration["OpenIddict:CertificatePath"],
        configuration["OpenIddict:CertificatePassword"]);
});
```

Don't hardcode the `.pfx` password (or check the certificate into source control) — read it from configuration, an environment variable, or a secret store, and keep the certificate out of the repository.

Notes:

- `AddDevelopmentEncryptionAndSigningCertificate` cannot be used on IIS or Azure App Service unless the app pool loads a user profile — it throws at runtime otherwise. Use real certificates stored in the machine's X.509 store instead. See <https://documentation.openiddict.com/configuration/encryption-and-signing-credentials.html>
- `AddProductionEncryptionAndSigningCertificate` is an ABP extension method (`OpenIddictServerBuilderExtensions` in `Volo.Abp.OpenIddict.AspNetCore`): it loads a `.pfx` and registers it as both the signing and encryption certificate. `AddSigningCertificate` and `AddEncryptionCertificate` are the underlying OpenIddict calls; consult the OpenIddict docs for the overload you need.

## Access token encryption

ABP calls `builder.DisableAccessTokenEncryption()` by default (for compatibility — access tokens are readable JWTs). To re-enable encryption:

```csharp
PreConfigure<OpenIddictServerBuilder>(builder =>
{
    builder.Configure(options => options.DisableAccessTokenEncryption = false);
});
```

## Other useful options

- `AbpOpenIddictAspNetCoreOptions.UpdateAbpClaimTypes` (default `true`): maps `AbpClaimTypes` (UserId, Role, UserName, Email, etc.) onto the OpenIddict claim types (`sub`, `role`, `preferred_username`, ...). Set `false` only if you deliberately manage claim types yourself.
- `TokenCleanupOptions` (in `ConfigureServices`): controls the background job that prunes orphaned tokens/authorizations — `IsCleanupEnabled` (default `true`), `CleanupPeriod` (default 3,600,000 ms), `MinimumTokenLifespan` / `MinimumAuthorizationLifespan` (default 14 days).
- Claim destinations: to control whether a claim lands in the `access_token` and/or `id_token`, implement `IAbpOpenIddictClaimsPrincipalHandler` (call `claim.SetDestinations(...)`) and register it via `AbpOpenIddictClaimsPrincipalOptions.ClaimsPrincipalHandlers.Add<...>()`.

## Validation

- Build the auth server module; a compile confirms the `PreConfigure`/`Configure` wiring.
- Refresh tokens: after granting `refresh_token` + requesting `offline_access`, confirm the token response includes a `refresh_token` and that exchanging it returns a new `access_token`.
- Development HTTPS: with `DisableTransportSecurityRequirement = true`, confirm the `connect/*` endpoints respond over plain HTTP locally.
- Production certificates: with development certificates disabled, confirm the server starts and issues tokens signed/encrypted by your `.pfx` (and that it does not fall back to development certificates).
- Access-token encryption: decode the `access_token` — readable JWT when encryption is disabled (default), opaque when re-enabled.

## Common Pitfalls

- A cookie whose `ExpireTimeSpan` outlives the refresh token leaves the user with a valid local session but no way to silently refresh the `access_token`, so API calls start failing — keep the cookie lifetime and refresh-token lifetime aligned (it does not keep an expired token valid).
- Refresh tokens need **both** the `refresh_token` grant on the client **and** the `offline_access` scope on the request; missing either silently yields no refresh token. If the DB is already seeded, re-create the client after changing grant types.
- `AddDevelopmentEncryptionAndSigningCertificate` throws at runtime on IIS / Azure App Service unless the app pool loads a user profile — use real X.509 certificates there.
- Development certificates are user-specific and for development only; you must set `AddDevelopmentEncryptionAndSigningCertificate = false` and register production certificates for non-dev environments.
- Only disable the transport-security requirement in development — it removes the HTTPS requirement from all endpoints.

## References

- `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/modules/openiddict.md`
- `https://github.com/abpframework/abp/blob/rel-10.5/modules/openiddict/src/Volo.Abp.OpenIddict.AspNetCore/Volo/Abp/OpenIddict/AbpOpenIddictAspNetCoreModule.cs`
- OpenIddict docs: <https://documentation.openiddict.com>
