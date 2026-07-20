---
name: configure-swagger-openapi
description: >
  Wire up Swagger/OpenAPI for an ABP host with the Volo.Abp.Swashbuckle helpers, including OAuth/OIDC authorize flows and hiding framework endpoints.
  USE FOR: AddAbpSwaggerGen + UseAbpSwaggerUI setup, AddAbpSwaggerGenWithOAuth / AddAbpSwaggerGenWithOidc for interactive auth on the Swagger UI, AbpSwaggerOidcFlows, HideAbpEndpoints, a metadata/discovery address that differs from the issuer (k8s/docker), versioned SwaggerDoc definitions.
  DO NOT USE FOR: exposing application services as HTTP controllers (use expose-http-apis); generating C# client proxies for remote APIs (use consume-remote-services); choosing an API versioning strategy (use version-http-apis); configuring the OpenIddict token/authorization server or JWT validation itself (use configure-openiddict-authentication / configure-openiddict-validation).
license: MIT
---

# Configure Swagger / OpenAPI in ABP

ABP ships the `Volo.Abp.Swashbuckle` package (module `AbpSwashbuckleModule`) that wraps Swashbuckle with ABP-aware defaults — remote-stream schema mapping, an injected UI script, and one-line OAuth/OIDC authorize setup. Use its extension methods instead of the raw `AddSwaggerGen` / `UseSwaggerUI`.

## When to Use

- Standing up the Swagger UI on a `Web` / `HttpApi.Host` project with `AddAbpSwaggerGen` + `UseAbpSwaggerUI`.
- Adding an **Authorize** button that runs a real login flow: `AddAbpSwaggerGenWithOAuth` (authorization-code against an issuer) or `AddAbpSwaggerGenWithOidc` (OpenID Connect discovery, choose flows).
- Pointing the UI at a **discovery/metadata address that differs from the token issuer** (k8s/docker split-DNS) — that's the specific reason to pick OIDC over OAuth.
- Hiding ABP's built-in endpoints from the document with `HideAbpEndpoints`.
- Declaring one or more versioned documents via `SwaggerDoc("v1", ...)`.

## When Not to Use

- **Publishing app services as controllers** (Auto API Controllers, `[RemoteService]`) — use **expose-http-apis**.
- **Calling a remote ABP API from C#** (client proxies) — use **consume-remote-services**.
- **API versioning strategy** (query vs URL segment) — use **version-http-apis**.
- **Configuring the OpenIddict server or JWT bearer validation** — use **configure-openiddict-authentication** / **configure-openiddict-validation**. This skill only tells the Swagger UI where to authorize; it does not set up the auth server.

## Install

Already present in the startup template. If missing, from the `Web`/`HttpApi.Host` project folder:

```bash
abp add-package Volo.Abp.Swashbuckle
```

Then add the module dependency:

```csharp
[DependsOn(typeof(AbpSwashbuckleModule))]
public class MyHostModule : AbpModule { }
```

## Basic setup

`AddAbpSwaggerGen(Action<SwaggerGenOptions>?)` in `ConfigureServices`, `UseAbpSwaggerUI(Action<SwaggerUIOptions>?)` in `OnApplicationInitialization`. `UseAbpSwaggerUI` calls `UseSwaggerUI` under the hood, so you still register `app.UseSwagger()` yourself.

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddAbpSwaggerGen(options =>
    {
        options.SwaggerDoc("v1", new OpenApiInfo { Title = "Test API", Version = "v1" });
        options.DocInclusionPredicate((docName, description) => true);
        options.CustomSchemaIds(type => type.FullName);
    });
}

public override void OnApplicationInitialization(ApplicationInitializationContext context)
{
    var app = context.GetApplicationBuilder();
    app.UseSwagger();
    app.UseAbpSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/swagger/v1/swagger.json", "Test API");
    });
}
```

Add another `SwaggerDoc("v2", ...)` + a matching `SwaggerEndpoint(...)` per version to expose multiple documents.

## Authorization on the Swagger UI

Non-MVC / non-tiered hosts need Swagger wired to your auth server so the **Authorize** button works. Two helpers — pick by whether the discovery address matches the issuer.

### OAuth (issuer == the URL the browser reaches)

`AddAbpSwaggerGenWithOAuth(authority, scopes, setupAction?, authorizationEndpoint = "/connect/authorize", tokenEndpoint = "/connect/token")` registers an `oauth2` authorization-code scheme. It derives the authorize/token URLs from `authority` + those endpoint paths.

```csharp
context.Services.AddAbpSwaggerGenWithOAuth(
    authority: "https://localhost:44341",
    scopes: new Dictionary<string, string> { { "Test", "Test API" } },
    options =>
    {
        options.SwaggerDoc("v1", new OpenApiInfo { Title = "Test API", Version = "v1" });
    });
```

Supply the client on the UI side (values must match an OpenIddict application configured elsewhere). The Swagger UI is a **public (browser) client** — it runs in the user's browser and can't keep a secret, so set the client id and scopes with the authorization-code flow and register the client with **no secret** (ABP's template registers the Swagger client as a public client). Don't call `OAuthClientSecret` here.

```csharp
app.UseAbpSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "Test API");
    options.OAuthClientId("Test_Swagger");
    options.OAuthScopes("Test");
});
```

### OIDC (discovery/metadata address differs from the issuer)

Use `AddAbpSwaggerGenWithOidc(authority, scopes?, flows?, discoveryEndpoint?, setupAction?, oidcAuthenticationScheme = "oidc")` when the browser must reach the OpenID discovery document (`.well-known/openid-configuration`) at a **different** URL than the internal issuer — e.g. app deployed to a Kubernetes cluster or Docker swarm, where the public DNS resolves the metadata over the internet but tokens are validated on the internal network.

```csharp
context.Services.AddAbpSwaggerGenWithOidc(
    authority: configuration["AuthServer:Authority"],
    scopes: new[] { "SwaggerDemo" },
    flows: new[] { AbpSwaggerOidcFlows.AuthorizationCode },
    // null => derive discovery from `authority`; set to the public DNS on k8s/docker
    discoveryEndpoint: configuration["AuthServer:Authority"],
    options =>
    {
        options.SwaggerDoc("v1", new OpenApiInfo { Title = "SwaggerDemo API", Version = "v1" });
    });
```

`flows` is a `string[]` of `AbpSwaggerOidcFlows` constants (each shows as a choice in the Authorize modal):

- `AbpSwaggerOidcFlows.AuthorizationCode` (`"authorization_code"`) — default & recommended; no client secret required.
- `AbpSwaggerOidcFlows.Implicit` (`"implicit"`) — deprecated JS-app flow.
- `AbpSwaggerOidcFlows.Password` (`"password"`) — ROPC; needs username, password, client secret.
- `AbpSwaggerOidcFlows.ClientCredentials` (`"client_credentials"`) — server-to-server.

Pass `flows: null` to fall back to `AuthorizationCode`. Pass `discoveryEndpoint: null` to derive discovery from `authority`.

## Hide ABP's endpoints

Call `HideAbpEndpoints()` on the `SwaggerGenOptions` to drop ABP's framework endpoints from the generated document:

```csharp
context.Services.AddAbpSwaggerGen(options =>
{
    options.HideAbpEndpoints();
});
```

Related `SwaggerGenOptions` helpers in the same package: `UserFriendlyEnums()` (readable enum schemas) and `CustomAbpSchemaIds()` (collision-safe schema ids for generic types).

## Validation

- Run the host and open `/swagger`. The UI loads and each `SwaggerDoc(...)` you declared shows in the document dropdown.
- Fetch `/swagger/v1/swagger.json` and confirm your paths are present; after `HideAbpEndpoints()`, ABP's framework endpoints are gone.
- With OAuth/OIDC, click **Authorize** — the modal should show your scopes (and, for OIDC, the flows you passed) and complete a real login round-trip.

## Common Pitfalls

- `UseAbpSwaggerUI` does **not** register `UseSwagger()` for you — add `app.UseSwagger()` before it or the `swagger.json` endpoint 404s.
- OAuth vs OIDC is not about "OpenIddict vs something else" — both target an OpenIddict server. Choose **OIDC** specifically when the reachable **discovery/metadata address differs from the issuer** (k8s/docker); otherwise **OAuth** is simpler.
- If the Authorize modal fails to appear with OIDC, the `discoveryEndpoint` is usually wrong or unreachable from the browser — check the browser console; the discovery URL must resolve `.well-known/openid-configuration` over the network the browser uses.
- `AddAbpSwaggerGenWithOAuth` only registers the scheme; you still must set `OAuthClientId` (and `OAuthScopes`) in `UseAbpSwaggerUI`, matching a **public** client registered in your auth server (that registration belongs to the OpenIddict skills, not here). Don't set a client secret for the browser-based Swagger UI.
