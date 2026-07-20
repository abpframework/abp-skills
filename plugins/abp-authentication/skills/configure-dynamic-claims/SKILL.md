---
name: configure-dynamic-claims
description: >
  Refresh a user's claims (roles, profile claims, and custom claims added to DynamicClaims) mid-session without re-login — enabling ABP dynamic claims, wiring the middleware, and adding a custom claims contributor in monolith or tiered/microservice setups. (Permissions are not part of the default dynamic-claims set.)
  USE FOR: IsDynamicClaimsEnabled on AbpClaimsPrincipalFactoryOptions, UseDynamicClaims middleware, RemoteRefreshUrl in tiered apps, IAbpDynamicClaimsPrincipalContributor, IsRemoteRefreshEnabled / WebRemoteDynamicClaimsPrincipalContributorOptions, choosing which DynamicClaims types refresh.
  DO NOT USE FOR: configuring the auth server itself (token lifetimes, certificates, refresh tokens) — use the configure-openiddict-authentication skill; defining/checking permissions — use the permissions-and-authorization skill; per-entity resource access — use the authorize-resources skill.
license: MIT
---

# Configure Dynamic Claims in ABP

When a user authenticates, the claims baked into the access token or auth cookie stay fixed until they re-authenticate. For claims that must take effect immediately after they change (e.g. a role revoked from a user), ABP's **dynamic claims** feature overrides the token/cookie claim values with the latest values on each request. The default `DynamicClaims` set covers roles, profile claims (user name, name/surname, email, phone), and any custom claims explicitly added to `DynamicClaims` — **not** permission claims. Permission changes are handled by the permission system, not lumped into dynamic claims.

Enabled by default in startup templates from v8.0+. If you created your solution on v8.0 or later, it already works and you don't need to configure anything below. Follow these steps only when upgrading from an older version or building a custom host.

## When to Use

- Claims (roles, profile claims, custom claims added to `DynamicClaims`) must refresh mid-session without forcing a re-login.
- Upgrading a solution created before v8.0, or building a custom host that authenticates.
- Wiring dynamic claims across a tiered structure (separate UI app + auth server) or microservice / resource-server apps.
- Adding a custom `IAbpDynamicClaimsPrincipalContributor`.

## When Not to Use

- **Configuring the auth server itself** (token lifetimes, certificates, refresh tokens) — use the **configure-openiddict-authentication** skill instead.
- **Defining or checking permissions** — use the **permissions-and-authorization** skill.
- **Access that depends on a specific entity instance** — use the **authorize-resources** skill.
- Solutions created on v8.0+ where dynamic claims already work out of the box — no configuration needed.

## Enable it

Set `IsDynamicClaimsEnabled` on `AbpClaimsPrincipalFactoryOptions`. This is normally done on the authentication server:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.Configure<AbpClaimsPrincipalFactoryOptions>(options =>
    {
        options.IsDynamicClaimsEnabled = true;
    });
}
```

## Add the middleware

Add the middleware in every application that authenticates (including the auth server), **before** `UseAuthorization`:

```csharp
public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();
    //...
    app.UseDynamicClaims(); // before UseAuthorization
    app.UseAuthorization();
    //...
}
```

`AbpDynamicClaimsMiddleware` only acts on authenticated requests when `IsDynamicClaimsEnabled` is `true`. It calls `IAbpClaimsPrincipalFactory.CreateDynamicAsync(context.User)` to rebuild the principal and replaces the `IAuthenticateResultFeature` ticket with the refreshed claims. If the refresh determines the user is no longer authenticated, it signs the user out of that scheme (when the scheme's handler supports sign-out).

## Tiered / separate UI application

In a tiered structure the UI is a separate app from the auth server. Enable dynamic claims and point `RemoteRefreshUrl` at the auth server:

```csharp
context.Services.Configure<AbpClaimsPrincipalFactoryOptions>(options =>
{
    options.IsDynamicClaimsEnabled = true;
    options.RemoteRefreshUrl = configuration["AuthServerUrl"] + options.RemoteRefreshUrl;
});
```

`RemoteRefreshUrl` defaults to `/api/account/dynamic-claims/refresh` and must be a full URL to the auth server in the UI app. It is already wired inside `AddAbpOpenIdConnect` and `AddAbpJwtBearer`, so you often don't need to set it explicitly.

## How it works — the contributors

The factory runs `IAbpDynamicClaimsPrincipalContributor` implementations. Three are pre-built:

- `IdentityDynamicClaimsPrincipalContributor` (Identity module): generates the real dynamic claims and writes them to the distributed cache. Runs on the auth server side.
- `RemoteDynamicClaimsPrincipalContributor`: runs in the UI app of a distributed system. Reads values from the distributed cache; if missing, makes an HTTP call to `RemoteRefreshUrl` on the auth server. Requires `RemoteRefreshUrl` to be set correctly.
- `WebRemoteDynamicClaimsPrincipalContributor`: like the remote contributor but for microservice / resource-server apps.

### RemoteRefreshEnabled — the key gotcha

`AbpClaimsPrincipalFactoryOptions.IsRemoteRefreshEnabled` controls whether the two **remote** contributors get registered. It is `true` by default, but the **Identity module sets it to `false`**.

That means: any app that includes the Identity module builds dynamic claims **locally** (via `IdentityDynamicClaimsPrincipalContributor`) and does **not** register the remote contributors — even if you set `WebRemoteDynamicClaimsPrincipalContributorOptions.IsEnabled = true`. The remote/web-remote contributors are meant for the resource-server / microservice side that authenticates against a remote auth server, not for the auth server itself.

`WebRemoteDynamicClaimsPrincipalContributorOptions`:

- `IsEnabled` (default `false`): enables `WebRemoteDynamicClaimsPrincipalContributor` — but only registers when `IsRemoteRefreshEnabled` is also `true`.
- `AuthenticationScheme`: scheme used to authenticate the HTTP call to the auth server.

### Which claim types are refreshed

`AbpClaimsPrincipalFactoryOptions.DynamicClaims` is the list of claim types the dynamic system is authoritative for. Only these get overridden.

Caveat: adding a type here makes the cache the source of truth for it. Whatever fills the cache (the Identity-side factory in the local case) must actually produce that claim, otherwise it gets cached as null and stripped from the principal on every refresh.

`AbpClaimsPrincipalFactoryOptions.ClaimsMap` maps claim types when they differ between the auth server and the client (pre-populated for common types).

## Custom contributor

Implement `IAbpDynamicClaimsPrincipalContributor` and register it in DI. ABP calls `ContributeAsync` on each eligible authenticated request — the middleware only refreshes when the request is authenticated, dynamic claims are enabled, and there is a valid `IAuthenticateResultFeature` with an authentication scheme — so cache aggressively.

```csharp
public class MyDynamicClaimsContributor : IAbpDynamicClaimsPrincipalContributor, ITransientDependency
{
    public async Task ContributeAsync(AbpClaimsPrincipalContributorContext context)
    {
        // read the current identity from context, add/override claims,
        // ideally from a cache since this runs per request
    }
}
```

## Validation

- Build each authenticating app; a compile confirms the `Configure` and `UseDynamicClaims` wiring.
- Confirm `app.UseDynamicClaims()` sits **before** `app.UseAuthorization()` in the pipeline.
- Change a user's role on the auth server, then make a request without re-login and confirm the new claim value takes effect immediately. The default `DynamicClaims` set covers user name, name/surname, roles, email, and phone — **not** permission claims — so only those refresh through this pipeline unless you add more. Revoking a role/permission does **not** force a sign-out on its own: the middleware only calls `SignOutAsync` when the refreshed identity comes back unauthenticated — which the identity contributor produces when the user no longer exists.
- Tiered setup: confirm `RemoteRefreshUrl` resolves to a full auth-server URL and the UI app can reach `/api/account/dynamic-claims/refresh`.

## Common Pitfalls

- The Identity module sets `IsRemoteRefreshEnabled = false`, so an app that includes Identity refreshes claims **locally** and never registers the remote/web-remote contributors — even with `WebRemoteDynamicClaimsPrincipalContributorOptions.IsEnabled = true`. Those contributors are for the resource-server / microservice side, not the auth server.
- `app.UseDynamicClaims()` must be registered **before** `app.UseAuthorization()`; wrong order means the refreshed principal is not in effect when authorization runs.
- Adding a claim type to `DynamicClaims` makes the cache authoritative for it — if the cache-filling factory does not actually produce that claim, it is cached as null and stripped from the principal on every refresh.
- In a tiered app, `RemoteRefreshUrl` must be a full URL to the auth server; the default `/api/account/dynamic-claims/refresh` alone is not enough in the UI app.
- The contributor runs per authenticated request, so cache aggressively inside `ContributeAsync`.

## References

- `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/fundamentals/dynamic-claims.md`
- `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.AspNetCore/Volo/Abp/AspNetCore/Security/Claims/AbpDynamicClaimsMiddleware.cs`
- `UseDynamicClaims`: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.AspNetCore/Microsoft/AspNetCore/Builder/AbpApplicationBuilderExtensions.cs`
- `IAbpClaimsPrincipalFactory.CreateDynamicAsync`: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Security/Volo/Abp/Security/Claims/IAbpClaimsPrincipalFactory.cs`
