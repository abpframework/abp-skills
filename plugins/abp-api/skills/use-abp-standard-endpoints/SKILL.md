---
name: use-abp-standard-endpoints
description: >
  Use ABP's built-in application-configuration and application-localization HTTP endpoints, and extend them with an IApplicationConfigurationContributor.
  USE FOR: reading /api/abp/application-configuration (current user, granted policies, settings, features, multi-tenancy, timing) and /api/abp/application-localization from a custom client; extending the config with IApplicationConfigurationContributor and AbpApplicationConfigurationOptions.
  DO NOT USE FOR: publishing your own application services as controllers (use expose-http-apis); calling remote ABP APIs with C# client proxies (use consume-remote-services); consuming the config in Angular/Blazor/MVC startup (use the per-stack UI skill: angular-ui / blazor-ui / mvc-razor-ui); defining settings/features themselves (use manage-settings-and-features); defining permissions (use permissions-and-authorization).
license: MIT
---

# Use ABP Standard Application Endpoints

Every ABP host ships two pre-built HTTP endpoints that describe the running application/service to its clients: `/api/abp/application-configuration` and `/api/abp/application-localization`. Official UI clients call these on startup; you only touch them directly when building a client from scratch or extending what they return.

## When to Use

- Reading `/api/abp/application-configuration` to get the current user, granted permissions (policies), setting values, features, multi-tenancy info, timing/clock, object extensions.
- Reading `/api/abp/application-localization` to pull localization resources and texts for a culture.
- Extending the configuration endpoint with your own data via `IApplicationConfigurationContributor` + `AbpApplicationConfigurationOptions`.
- Building a non-official client (a custom SPA, a mobile app, a service) that needs the same bootstrap data ABP's UIs consume.

## When Not to Use

- **Exposing your own application services as REST controllers** — use the **expose-http-apis** skill.
- **Calling a remote ABP API from C#** (client proxies, `AbpRemoteServiceOptions`) — use the **consume-remote-services** skill.
- **Consuming this config inside Angular/Blazor/MVC at startup** (`ConfigStateService`, `abp.currentUser`, etc.) — use the per-stack UI skill (**angular-ui** / **blazor-ui** / **mvc-razor-ui**).
- **Defining the settings/features** that show up here — use **manage-settings-and-features**.
- **Defining the permissions** whose grants show up under `Auth.GrantedPolicies` — use **permissions-and-authorization**.

## How it works

### The application-configuration endpoint

Served by `AbpApplicationConfigurationAppService` (implements `IAbpApplicationConfigurationAppService`), exposed through `AbpApplicationConfigurationController`:

- Route: `[Route("api/abp/application-configuration")]`, verb `[HttpGet]`, `[RemoteService(Name = "abp")]`, `[Area("abp")]`.
- Binds an `ApplicationConfigurationRequestOptions` from the query string. It has one property, `IncludeLocalizationResources` (default `true`); set it to `false` to skip filling the localization `Values` (useful when the client already shares the localization files).
- The controller also calls `AntiForgeryManager.SetCookie()` on each request, so hitting this endpoint issues the anti-forgery cookie.

`GetAsync` returns `ApplicationConfigurationDto`, whose real shape is:

| Property | Type | Contents |
| --- | --- | --- |
| `Auth` | `ApplicationAuthConfigurationDto` | `GrantedPolicies` — the policies/permissions granted to the current user |
| `Setting` | `ApplicationSettingConfigurationDto` | client-visible setting values (`IsVisibleToClients`) |
| `CurrentUser` | `CurrentUserDto` | `IsAuthenticated`, `Id`, `TenantId`, `UserName`, `Name`, `SurName`, `Email`, `EmailVerified`, `PhoneNumber`, `PhoneNumberVerified`, `Roles`, `SessionId`, impersonation fields |
| `Features` | `ApplicationFeatureConfigurationDto` | client-visible feature values |
| `GlobalFeatures` | `ApplicationGlobalFeatureConfigurationDto` | `EnabledFeatures` |
| `MultiTenancy` | `MultiTenancyInfoDto` | `IsEnabled`, `UserSharingStrategy` |
| `CurrentTenant` | `CurrentTenantDto` | `Id`, `Name`, `IsAvailable` |
| `Localization` | `ApplicationLocalizationConfigurationDto` | languages, current culture, resource values (when `IncludeLocalizationResources`) |
| `Timing` | `TimingDto` | current user's time zone (Windows + IANA) |
| `Clock` | `ClockDto` | `Kind` (the `AbpClockOptions.Kind`, e.g. `Utc`/`Local`) |
| `ObjectExtensions` | `ObjectExtensionsDto` | extra-property/extensible-object metadata |
| `ExtraProperties` | `ExtraPropertyDictionary` | anything added by contributors |

Only client-visible settings (`IsVisibleToClients`) and client-visible features are included; the app service filters both.

### The application-localization endpoint

Served by `AbpApplicationLocalizationAppService` (implements `IAbpApplicationLocalizationAppService`), exposed through `AbpApplicationLocalizationController`:

- Route: `[Route("api/abp/application-localization")]`, verb `[HttpGet]`, `[RemoteService(Name = "abp")]`, `[Area("abp")]`.
- Binds `ApplicationLocalizationRequestDto` from the query string:
  - `CultureName` (`[Required]`) — a culture code like `en` or `en-US`. `GetAsync` throws `AbpException` if it isn't a valid culture code.
  - `OnlyDynamics` (default `false`) — set to `true` to return only dynamically-defined texts. When your client shares the same static localization files as the server (like ABP's Blazor/MVC UIs), pass `true` so you only download the dynamic delta.

Returns `ApplicationLocalizationDto`: `Resources` (a dictionary of resource name → `ApplicationLocalizationResourceDto` with `Texts` and `BaseResources`) plus `CurrentCulture`.

Example request:

```text
GET /api/abp/application-localization?cultureName=en&onlyDynamics=true
```

Note the naming split: the `application-configuration` endpoint carries a **languages list and (optionally) resource values** in its `Localization` property; `application-localization` is the dedicated endpoint for the **full per-culture texts**.

### Extending the configuration with a contributor

To add your own data to `application-configuration`, implement `IApplicationConfigurationContributor` (namespace `Volo.Abp.AspNetCore.Mvc.ApplicationConfigurations`), which defines a single method `ContributeAsync(ApplicationConfigurationContributorContext context)`:

```csharp
using System.Threading.Tasks;
using Volo.Abp.AspNetCore.Mvc.ApplicationConfigurations;
using Volo.Abp.Data;

public class MyApplicationConfigurationContributor : IApplicationConfigurationContributor
{
    public Task ContributeAsync(ApplicationConfigurationContributorContext context)
    {
        // resolve any service from context.ServiceProvider and run your logic
        context.ApplicationConfiguration.SetProperty("deploymentVersion", "v1.0.0");
        return Task.CompletedTask;
    }
}
```

`ApplicationConfigurationContributorContext` exposes `ServiceProvider` (contributors run inside a fresh DI scope) and `ApplicationConfiguration` (the `ApplicationConfigurationDto` being built). `SetProperty(...)` lands the value in the DTO's `ExtraProperties`.

Register the contributor instance in `AbpApplicationConfigurationOptions.Contributors`:

```csharp
Configure<AbpApplicationConfigurationOptions>(options =>
{
    options.Contributors.AddIfNotContains(new MyApplicationConfigurationContributor());
});
```

`AbpApplicationConfigurationOptions` has exactly one member, `Contributors` (a `List<IApplicationConfigurationContributor>`). The app service runs every registered contributor after building the standard DTO, so contributors can also read/adjust the already-populated properties, not just add extras.

## Validation

- `GET /api/abp/application-configuration` returns JSON with `auth.grantedPolicies`, `currentUser`, `setting`, `features`, `multiTenancy`, `currentTenant`, `timing`, `clock`.
- Sign in and confirm `currentUser.isAuthenticated` flips to `true` and `auth.grantedPolicies` lists the granted permission names.
- `GET /api/abp/application-configuration?includeLocalizationResources=false` returns the same DTO but with `localization.values` empty.
- `GET /api/abp/application-localization?cultureName=en` returns `resources` keyed by resource name; add `&onlyDynamics=true` and confirm only the dynamic texts come back.
- After registering a contributor, confirm the extra key (e.g. `deploymentVersion`) appears under `extraProperties` of the configuration response.
- An invalid `cultureName` on the localization endpoint throws a plain `AbpException`, which ABP's default exception-to-status-code mapping surfaces as **500** (a bare `AbpException` is not treated as a validation/4xx error).

## Common Pitfalls

- The contributor interface is **`IApplicationConfigurationContributor`** (no `Abp` prefix), even though the *options* type is `AbpApplicationConfigurationOptions` and the *app service* is `AbpApplicationConfigurationAppService`. Don't invent `IAbpApplicationConfigurationContributor`.
- Only settings/features flagged `IsVisibleToClients` reach the client. A setting missing from `setting.values` usually means it isn't client-visible, not that the endpoint dropped it — fix it where the setting/feature is defined (**manage-settings-and-features**).
- `onlyDynamics=true` returns only the dynamic delta; a client that doesn't also ship the static localization files will be missing texts. Use it only when the client shares the server's static resources.
- Don't reach for this endpoint to consume config inside an official UI — the UI framework already loads it into its own state service on startup (**angular-ui** / **blazor-ui** / **mvc-razor-ui**). Hitting the raw endpoint yourself is for custom/from-scratch clients.
- `IncludeLocalizationResources` defaults to `true`, so an unqualified request downloads all localization values on every call; pass `false` when the client already has them.
