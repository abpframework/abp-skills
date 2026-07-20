---
name: manage-settings-and-features
description: "ABP settings (config values) and features (tenant/edition on/off or valued capabilities). USE FOR: SettingDefinitionProvider / ISettingProvider, FeatureDefinitionProvider / IFeatureChecker / [RequiresFeature], custom value providers, ISettingManager and IFeatureManager. DO NOT USE FOR: typed distributed caching or locking (distributed-caching-and-locking); user/role authorization (permissions-and-authorization); multi-tenant resolution (configure-multi-tenancy)."
license: MIT
---

# Managing Settings and Features in ABP

Settings and features look similar (both are name/value pairs resolved through a provider fallback chain) but answer different questions:

- **Settings** = configuration values for the application/tenant/user (SMTP host, default timezone, page size). Resolved per user > tenant > global > configuration > default. Used everywhere, not tied to multi-tenancy.
- **Features** = capabilities you grant to a **tenant** (or edition), usually boolean on/off or a limit value (max product count). Designed for SaaS/multi-tenant: "does this tenant's plan include PDF reporting?".

Rule of thumb: if a customer's plan/edition controls it, it's a feature; if it's a tunable configuration value, it's a setting.

## When to Use

- Declare tunable configuration values (SMTP host, page size) and read them with provider fallback.
- Grant per-tenant or per-edition capabilities (on/off or valued) for a SaaS app.
- Gate a service method or class behind a feature declaratively or imperatively.
- Change setting or feature values from code, or add a custom value provider.

## When Not to Use

- **Typed distributed caching or cross-instance locking** — use the **distributed-caching-and-locking** skill.
- **Authorizing users/roles with permissions** — use the **permissions-and-authorization** skill. Features gate a tenant's *plan*, permissions gate a *user's* rights.
- **Configuring or resolving multi-tenancy itself** — use the **configure-multi-tenancy** skill.

## Settings

### Defining settings

Derive from `SettingDefinitionProvider` (auto-discovered, transient). For a DDD module this usually lives in the `Domain` layer.

```csharp
public class EmailSettingProvider : SettingDefinitionProvider
{
    public override void Define(ISettingDefinitionContext context)
    {
        context.Add(
            new SettingDefinition("Smtp.Host", "127.0.0.1"),
            new SettingDefinition("Smtp.Port", "25"),
            new SettingDefinition("Smtp.UserName"),
            new SettingDefinition("Smtp.Password", isEncrypted: true),
            new SettingDefinition("Smtp.EnableSsl", "false")
        );
    }
}
```

`SettingDefinition` constructor parameters (only `name` is mandatory):
`name`, `defaultValue = null`, `displayName = null`, `description = null`, `isVisibleToClients = false`, `isInherited = true`, `isEncrypted = false`.

- `IsVisibleToClients` defaults to **false** — set it true to expose the value to browser/JS code.
- `IsEncrypted` encrypts on save / decrypts on read via `ISettingEncryptionService`.
- Define setting names as `const string` instead of magic strings.

To tweak a setting defined by a depended module, query and mutate it in your own provider:

```csharp
var smtpHost = context.GetOrNull("Abp.Mailing.Smtp.Host");
if (smtpHost != null)
{
    smtpHost.DefaultValue = "mail.mydomain.com";
}
```

### Reading setting values

Inject `ISettingProvider`. Its interface methods are `GetOrNullAsync(name)` → `Task<string?>`, `GetAllAsync(string[] names)` and `GetAllAsync()` → `Task<List<SettingValue>>`; the typed/bool helpers like `IsTrueAsync` and `GetAsync<T>` are extension methods.

```csharp
string? userName = await _settingProvider.GetOrNullAsync("Smtp.UserName");
bool enableSsl  = await _settingProvider.IsTrueAsync("Smtp.EnableSsl");
int port        = await _settingProvider.GetAsync<int>("Smtp.Port"); // defaultValue optional
```

`IApplicationService` already property-injects `ISettingProvider` (use the `SettingProvider` property).

### Value providers and store

`ISettingProvider` resolves a value by walking 5 built-in providers; the first that returns non-null wins. Fallback goes bottom → top:

`UserSettingValueProvider` (U) > `TenantSettingValueProvider` (T) > `GlobalSettingValueProvider` (G) > `ConfigurationSettingValueProvider` (C) > `DefaultValueSettingValueProvider` (D).

- Configuration provider reads the `"Settings"` section of `appsettings.json` (or env / user secrets).
- Global/Tenant/User providers read through `ISettingStore`. The core ships `NullSettingStore` (always null); the **Setting Management module** implements a database-backed `ISettingStore` — that's what actually persists changed values.
- Custom provider: derive from `SettingValueProvider` (unique `Name`), then register via `Configure<AbpSettingOptions>(o => o.ValueProviders.Add<CustomSettingValueProvider>())`.

## Features

### Defining features

Derive from `FeatureDefinitionProvider` (auto-discovered). Usually placed in the `Application.Contracts` project. You add a **group** first, then features under it.

```csharp
using Volo.Abp.Features;
using Volo.Abp.Validation.StringValues;

public class MyFeatureDefinitionProvider : FeatureDefinitionProvider
{
    public override void Define(IFeatureDefinitionContext context)
    {
        var myGroup = context.AddGroup("MyApp");

        myGroup.AddFeature("MyApp.PdfReporting", defaultValue: "false");

        myGroup.AddFeature(
            "MyApp.MaxProductCount",
            defaultValue: "10",
            valueType: new FreeTextStringValueType(new NumericValueValidator(0, 1000000))
        );
    }
}
```

Optional feature properties: `DisplayName`, `Description`, `ValueType` (`ToggleStringValueType` for on/off, `FreeTextStringValueType` for free text, `SelectionStringValueType` for a dropdown), `IsVisibleToClients` (default **true**), `Properties`.

Child features (selectable only when the parent is enabled) via `CreateChild(...)` on the returned `FeatureDefinition`. Modify a depended module's feature with `context.GetGroupOrNull("SomeModule")`.

### Checking features

Two ways: the declarative `[RequiresFeature]` attribute or the `IFeatureChecker` service.

```csharp
public class ReportingAppService : ApplicationService, IReportingAppService
{
    [RequiresFeature("MyApp.PdfReporting")] // throws AbpAuthorizationException if not enabled
    public async Task<PdfReportResultDto> GetPdfReportAsync() { return await GenerateReportAsync(); }
}
```

- `[RequiresFeature]` works on a method or a class. Multiple names check "any enabled"; set `RequiresAll = true` to require all.
- It relies on interception: for non-interface services methods must be `virtual` (class-proxy requirement); an `async`/Task-returning method is recommended but not required. Controllers/Razor pages are exempt (filters handle them).

`IFeatureChecker` for imperative checks. Interface methods: `IsEnabledAsync(name)`, `IsEnabledAsync(string[] names)`, `GetOrNullAsync(name)` → `Task<string?>`. Typed/check helpers are extensions.

```csharp
if (await _featureChecker.IsEnabledAsync("MyApp.PdfReporting")) { /* ... */ }

int max = await _featureChecker.GetAsync<int>("MyApp.MaxProductCount");

await _featureChecker.CheckEnabledAsync("MyApp.PdfReporting"); // throws if disabled
```

### Value providers, management, and configuration

Feature values resolve through providers (first non-null wins), in order:
`TenantFeatureValueProvider` > `EditionFeatureValueProvider` (edition id from `AbpClaimTypes.EditionId`) > `ConfigurationFeatureValueProvider` (reads the `"Features"` section of `appsettings.json`) > `DefaultValueFeatureValueProvider`.

Custom provider: derive from `FeatureValueProvider`, register via `Configure<AbpFeatureOptions>(o => o.ValueProviders.Add<...>())`.

Persistence is `IFeatureStore` — the **Feature Management module** implements it (DB-backed) and ships in the startup template. To change feature values from code inject `IFeatureManager`:

```csharp
await _featureManager.SetForTenantAsync(tenantId, "MyApp.PdfReporting", true.ToString());
```

Admins normally set feature values via the feature-management modal on the Tenant Management page.

To change **setting** values from code, inject `ISettingManager` (namespace `Volo.Abp.SettingManagement`, from the **Setting Management module** package `Volo.Abp.SettingManagement.Domain`). It persists to the correct provider scope:

```csharp
await _settingManager.SetGlobalAsync("MyApp.SmtpHost", "smtp.acme.com");
await _settingManager.SetForTenantAsync(tenantId, "MyApp.SmtpHost", "smtp.tenant.com");
await _settingManager.SetForUserAsync(userId, "MyApp.Theme", "dark");
```

`ISettingProvider` (read) is in the framework, but writing needs the Setting Management module — a host that only references `Volo.Abp.Settings` can read but not persist changes.

## Validation

- Build the app; `SettingDefinitionProvider` and `FeatureDefinitionProvider` are auto-discovered at startup.
- Read a setting back through `ISettingProvider` and confirm the fallback resolves the expected layer (e.g. an `appsettings.json` `"Settings"` value overrides the default).
- Confirm a `[RequiresFeature]`-guarded method throws `AbpAuthorizationException` when the feature is disabled and runs when enabled.
- Confirm persisted values require the Setting Management / Feature Management module (the core `NullSettingStore` always returns null, so without it only configuration/default values resolve).

## Common Pitfalls

- **`[RequiresFeature]` silently not enforced** — it relies on interception, so for non-interface services the method must be `virtual` (class-proxy requirement). An `async`/Task-returning method is recommended but not required. Controllers/Razor pages are exempt (filters handle them instead).
- **Expecting changed setting/feature values to persist without the management module** — the core ships `NullSettingStore` (always null); DB persistence comes from the **Setting Management** / **Feature Management** modules.
- **Confusing features with permissions** — features gate a *tenant/edition's* plan, permissions gate a *user's* rights. Don't use a feature where a permission belongs.
- **`IsVisibleToClients` defaults differ** — settings default to **false** (hidden from browser/JS), features default to **true**. Set it explicitly when the default is wrong for your case.
- **Using magic strings for names** — define setting/feature names as `const string` to avoid typos that resolve to a missing (null) value.
