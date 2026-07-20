---
name: read-configuration
description: "Read and bootstrap Microsoft.Extensions.Configuration in ABP apps and modules. USE FOR: IConfiguration in AbpModule/services, ServiceConfigurationContext.Configuration, IServiceCollection.GetConfiguration, AbpApplicationCreationOptions.Configuration, ConfigurationHelper. DO NOT USE FOR: dynamic settings or tenant/user overrides (manage-settings-and-features); typed options binding (define-application-modules); connection strings (configure-connection-strings)."
license: MIT
---

# Reading Configuration in ABP

## When to Use

- Read host configuration during module service registration.
- Inject standard `IConfiguration` into an application service.
- Bootstrap configuration when creating an ABP application without a .NET host.
- Understand ABP's extra `appsettings.secrets.json` convention.

## When Not to Use

- **Values changed per user, tenant, or at runtime** — use manage-settings-and-features.
- **Typed options composition and pre-configuration** — use define-application-modules.
- **ABP connection-string resolution by database/module/tenant** — use configure-connection-strings.

## How it works

ABP is fully compatible with `Microsoft.Extensions.Configuration`; it does not replace the standard provider pipeline. The main ABP difference is convenient access during module initialization and optional bootstrap helpers for applications without an existing host configuration.

Inside an `AbpModule`, prefer `ServiceConfigurationContext.Configuration`:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    var endpoint = context.Configuration["ExternalApi:Endpoint"];
}
```

That property lazily calls `context.Services.GetConfiguration()`. If code has only an `IServiceCollection`, call `GetConfiguration()` directly. It throws `AbpException` when no `IConfiguration` implementation is registered; `GetConfigurationOrNull()` returns null instead.

In an ordinary service, use standard constructor injection:

```csharp
public class ExternalApiEndpointProvider : ITransientDependency
{
    private readonly IConfiguration _configuration;

    public ExternalApiEndpointProvider(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public string? GetEndpoint()
    {
        return _configuration["ExternalApi:Endpoint"];
    }
}
```

For ASP.NET Core and other .NET hosted applications, let the host build and register configuration. `AbpApplicationCreationOptions.Configuration` only takes effect when `IConfiguration` has not already been registered.

### ABP bootstrap helper

The verified ABP type is `Microsoft.Extensions.Configuration.ConfigurationHelper`, not `AbpConfigurationHelper`.

```csharp
var configuration = ConfigurationHelper.BuildConfiguration(
    new AbpConfigurationBuilderOptions
    {
        EnvironmentName = "Development",
        CommandLineArgs = args
    });
```

Verified `AbpConfigurationBuilderOptions` defaults:

- `FileName`: `"appsettings"`
- `Optional`: `true`
- `ReloadOnChange`: `true`
- `BasePath`: null, replaced with `Directory.GetCurrentDirectory()` by the helper
- `EnvironmentName`, `EnvironmentVariablesPrefix`, `CommandLineArgs`, `UserSecretsId`, and `UserSecretsAssembly`: null

`BuildConfiguration` adds providers in this order:

1. `{FileName}.json`
2. `{FileName}.secrets.json` as optional
3. `{FileName}.{EnvironmentName}.json` as optional when an environment is supplied
4. user secrets only when the environment name equals `"Development"` and a secrets ID or assembly is supplied
5. environment variables, with the optional prefix
6. command-line arguments when supplied
7. the optional `builderAction`, before `Build()`

Later configuration providers override earlier providers according to standard .NET configuration behavior.

`AddAppSettingsSecretsJson(optional: true, reloadOnChange: true, path: ...)` is also available on `IConfigurationBuilder` to add only ABP's secrets JSON convention to an existing builder.

## Validation

- In a hosted app, verify `context.Configuration` and injected `IConfiguration` resolve the same value.
- Override one JSON value with an environment variable or command-line argument and verify standard provider precedence.
- For a non-hosted app, verify `ConfigurationHelper.BuildConfiguration` reads the expected base path and environment-specific file.
- Verify user secrets are added only for the exact `"Development"` environment condition used by the helper.
- Verify `GetConfiguration()` fails clearly when configuration was never registered.

## Common Pitfalls

- **Using the nonexistent `AbpConfigurationHelper` name** — the class is `ConfigurationHelper` in the `Microsoft.Extensions.Configuration` namespace.
- **Rebuilding configuration inside every service** — inject the host's singleton `IConfiguration` instead.
- **Expecting ABP to use a different configuration model** — provider precedence, key syntax, binding, and environment variables remain standard .NET behavior.
- **Configuring `AbpApplicationCreationOptions.Configuration` in a hosted app and expecting it to override the host** — those options only apply when `IConfiguration` is not registered.
- **Putting runtime tenant/user values in appsettings** — use ABP settings for scoped, dynamically managed values.
