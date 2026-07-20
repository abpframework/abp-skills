---
name: toggle-global-features
description: "ABP Global Features toggled before startup to include/remove whole module capabilities. USE FOR: GlobalFeatureManager, GlobalFeature/GlobalModuleFeatures, GlobalFeatureConfigurator, [RequiresGlobalFeature], startup-time controller/page/database-model gating. DO NOT USE FOR: tenant/edition feature values or [RequiresFeature] (manage-settings-and-features); user/role permissions (permissions-and-authorization); runtime configuration flags (read-configuration)."
license: MIT
---

# Toggling Global Features in ABP

## When to Use

- Let an application opt into an optional capability of a reusable module.
- Hide controllers/pages from API Explorer / remote-service discovery (and return 404 at runtime) when a capability is disabled.
- Exclude database model pieces before migrations/model creation, when a module configures its model conditionally on the feature state.
- Group module-wide switches behind a discoverable `GlobalModuleFeatures` API.

## When Not to Use

- **Per-tenant or per-edition capabilities** — use manage-settings-and-features.
- **User/role access control** — use permissions-and-authorization.
- **A flag that changes while the application is running** — use configuration/settings or another runtime mechanism.

## How it works

Global Features are development/startup-time switches. They are disabled unless explicitly enabled. Configure them before application startup: a disabled controller/page/service stays in the application model but is hidden from API Explorer / remote-service discovery (`ApiExplorer.IsVisible = false`) and returns `404` at runtime, and a module can omit disabled database tables from its model. Neither behavior is re-evaluated after startup.

Define a named feature type:

```csharp
[GlobalFeatureName("Shopping.Payment")]
public class PaymentFeature
{
}
```

Enable, disable, and inspect it through the process-wide singleton:

```csharp
GlobalFeatureManager.Instance.Enable<PaymentFeature>();
GlobalFeatureManager.Instance.Disable("Shopping.Payment");

var enabled = GlobalFeatureManager.Instance.IsEnabled<PaymentFeature>();
```

Verified manager operations accept a generic feature type, `Type`, or string name. `GetEnabledFeatureNames()` returns the current enabled-name set as `IEnumerable<string>`.

### Configure once before startup

The startup template generates an application-specific class such as `MyProjectNameGlobalFeatureConfigurator`. This is a template convention, not a framework type named `GlobalFeatureConfigurator`. It wraps changes in `OneTimeRunner` and is called from the Domain.Shared module's `PreConfigureServices`:

```csharp
public static class MyAppGlobalFeatureConfigurator
{
    private static readonly OneTimeRunner OneTimeRunner = new();

    public static void Configure()
    {
        OneTimeRunner.Run(() =>
        {
            GlobalFeatureManager.Instance.Enable<PaymentFeature>();
        });
    }
}

public override void PreConfigureServices(ServiceConfigurationContext context)
{
    MyAppGlobalFeatureConfigurator.Configure();
}
```

### Guard a class

`RequiresGlobalFeatureAttribute` targets classes and accepts either a feature `Type` or a feature name:

```csharp
[RequiresGlobalFeature(typeof(PaymentFeature))]
public class PaymentController : AbpController
{
}
```

For MVC controllers/pages, a disabled global-feature component stays in the application model but the service convention sets its `ApiExplorer.IsVisible = false` (hidden from API Explorer and remote-service discovery), and `GlobalFeatureActionFilter`/`GlobalFeaturePageFilter` return a `NotFoundResult` (`404`) for requests at runtime. For intercepted services implementing `IGlobalFeatureCheckingEnabled`, the global-feature interceptor throws `AbpGlobalFeatureNotEnabledException`. The attribute does not target individual methods.

### Group a module's features

For a reusable module, derive each switch from `GlobalFeature`, derive a group from `GlobalModuleFeatures`, call `AddFeature(...)` in the group constructor, and expose an extension on `GlobalModuleFeaturesDictionary`. The group supports `Enable<TFeature>()`, `Disable<TFeature>()`, `SetEnabled<TFeature>(bool)`, string-name equivalents, `EnableAll()`, and `DisableAll()`.

```csharp
GlobalFeatureManager.Instance.Modules.Ecommerce().Subscription.Enable();
GlobalFeatureManager.Instance.Modules.Ecommerce().EnableAll();
```

Use this grouping only when authoring a reusable module API; application code enabling existing module features should use the module's supplied extension.

## Validation

- Start once with the feature disabled and verify the guarded controller/page returns `404` and is absent from the API Explorer / remote-service metadata.
- Enable it in `PreConfigureServices`, restart, and verify the component is reachable and any model configuration the module gates on the feature is present.
- Verify `IsEnabled<TFeature>()` and `GetEnabledFeatureNames()` reflect the startup configuration.
- For grouped features, verify `EnableAll()` enables every feature added to `AllFeatures`.
- Generate or apply migrations only after the intended global-feature set is configured.

## Common Pitfalls

- **Changing a Global Feature at runtime** — application models and database models may already be built; configure before startup and restart.
- **Confusing it with tenant features** — Global Features are process-wide startup switches, not tenant/edition values.
- **Assuming `GlobalFeatureConfigurator` is a framework API** — it is an application-specific class generated by templates.
- **Forgetting that features default to disabled** — explicitly enable required module capabilities.
- **Putting `[RequiresGlobalFeature]` on a method** — the attribute targets classes only.
- **Creating migrations under the wrong switch set** — database schema output can depend on enabled Global Features.
- **Expecting `GlobalFeatureManager` to trim the database model automatically** — it does not. A module must check `GlobalFeatureManager.Instance.IsEnabled<TFeature>()` inside its own `OnModelCreating`/model-configuration code to include or omit tables (e.g. CmsKit's `ConfigureCmsKit`).
