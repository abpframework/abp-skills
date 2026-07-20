---
name: configure-logging
description: "ABP startup, runtime, exception logging, and the startup-template Serilog bridge. USE FOR: typed ILogger in ABP services; IInitLoggerFactory/GetInitLogger startup buffering; ABP exceptions via LogException; Serilog via UseSerilog. DO NOT USE FOR: audit-log persistence and entity history (configure-audit-logging); distributed traces and metrics (out of scope, wire the OpenTelemetry .NET SDK directly); exception-to-HTTP response details (handle-validation-and-errors)."
license: MIT
---

# Configuring Logging in ABP

## When to Use

- Configure a logging provider for an ABP host.
- Log from application services through `ILogger<T>`.
- Understand logs emitted before the final service provider exists.
- Preserve ABP exception log levels, error metadata, and self-logging behavior.
- Follow the startup-template Serilog pattern.

## When Not to Use

- **Audit log persistence, contributors, or entity change history** — use configure-audit-logging.
- **Tracing, metrics, exporters, or telemetry sampling** — out of scope here; ABP ships no OpenTelemetry framework module, so wire the OpenTelemetry .NET SDK directly.
- **HTTP exception response mapping or client-visible details** — use handle-validation-and-errors.

## How it works

ABP does not replace `Microsoft.Extensions.Logging`. Register providers through the standard .NET host and inject `ILogger<T>` into services.

```csharp
public class ReportGenerator : ITransientDependency
{
    private readonly ILogger<ReportGenerator> _logger;

    public ReportGenerator(ILogger<ReportGenerator> logger)
    {
        _logger = logger;
    }

    public void Generate()
    {
        _logger.LogInformation("Generating report");
    }
}
```

### Early initialization logs

ABP registers `IInitLoggerFactory` before normal module registration. `IServiceCollection.GetInitLogger<T>()` returns a buffered initialization logger from that factory, or `NullLogger<T>.Instance` if the factory is unavailable. `DefaultInitLoggerFactory` caches loggers by category and retains `AbpInitLogEntry` items until application initialization transfers them to the configured `ILoggerFactory` and clears them.

Use this only in infrastructure that must log while services are still being registered:

```csharp
var logger = context.Services.GetInitLogger<MyAppModule>();
logger.LogDebug("Configuring module services");
```

No `IObjectAccessor<ILogger>`-based early logging registration exists in the ABP framework source. Do not document or add that older/unverified pattern.

### Exception logging

Use ABP's `ILogger.LogException(exception, optionalLevel)` extension when logging an ABP exception outside the automatic exception pipeline. Without an explicit level it calls `exception.GetLogLevel()`; the default is `Error`, while `BusinessException` defaults to `Warning` through `IHasLogLevel`.

`LogException` also logs known `IHasErrorCode`/`IHasErrorDetails` properties, invokes `IExceptionWithSelfLogging.Log(ILogger)`, and logs exception `Data`. Avoid following it with another `LogError` for the same exception.

ASP.NET Core exception middleware calls `LogException` unless an `AbpExceptionHandlingOptions.ExcludeExceptionFromLoggerSelectors` predicate excludes the exception.

### Serilog startup-template bridge

The application template creates the static bootstrap logger before building the host, then bridges the host to Serilog:

```csharp
Log.Logger = new LoggerConfiguration()
#if DEBUG
    .MinimumLevel.Debug()
#else
    .MinimumLevel.Information()
#endif
    .MinimumLevel.Override("Microsoft", LogEventLevel.Information)
    .MinimumLevel.Override("Microsoft.EntityFrameworkCore", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Async(c => c.File("Logs/logs.txt"))
    .WriteTo.Async(c => c.Console())
    .CreateLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);
    builder.Host.UseSerilog();
    await builder.AddApplicationAsync<MyAppModule>();
    var app = builder.Build();
    await app.InitializeApplicationAsync();
    await app.RunAsync();
}
catch (Exception exception)
{
    // The template rethrows HostAbortedException (e.g. from `dotnet ef`) instead of logging it as fatal.
    if (exception is HostAbortedException)
    {
        throw;
    }

    Log.Fatal(exception, "Host terminated unexpectedly!");
}
finally
{
    Log.CloseAndFlush();
}
```

The template uses `.MinimumLevel.Debug()` in DEBUG builds and `.MinimumLevel.Information()` otherwise, and rethrows `HostAbortedException` rather than logging it as fatal.

Keep provider-specific configuration in the host. Application and module code should normally depend on `ILogger<T>`, not Serilog's static `Log` API.

## Validation

- Start the application and confirm both early module logs and runtime `ILogger<T>` logs reach the configured sink.
- Throw a test `BusinessException` and verify automatic logging uses `Warning` unless explicitly changed.
- Test an `IExceptionWithSelfLogging` exception and verify its additional log is emitted once.
- Confirm `UseSerilog()` is called before `AddApplicationAsync`/host build.
- Shut down the host and verify buffered sinks are flushed.

## Common Pitfalls

- **Looking for `IObjectAccessor<ILogger>`** — early logging uses `IInitLoggerFactory` and `GetInitLogger<T>()`.
- **Treating audit logging as application logging** — audit records have a separate pipeline and storage model.
- **Double-logging handled exceptions** — ABP's exception middleware already logs caught exceptions.
- **Injecting Serilog types throughout application code** — prefer `ILogger<T>` so provider choice stays at the host boundary.
- **Creating the bootstrap logger after host construction** — startup failures before that point will not reach it.
- **Forgetting `Log.CloseAndFlush()`** — asynchronous/file sinks can retain buffered events.
