// Startup module for the runtime behavior tests: the minimal ABP application under test.
using System;
using System.ComponentModel.DataAnnotations;
using System.Threading;
using System.Threading.Tasks;
using AutoMapper;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.AutoMapper;
using Volo.Abp.Authorization;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.Autofac;
using Volo.Abp.Caching;
using Volo.Abp.DependencyInjection;
using Volo.Abp.DynamicProxy;
using Volo.Abp.EventBus;
using Volo.Abp.EventBus.Local;
using Volo.Abp.Modularity;
using Volo.Abp.Settings;
using Volo.Abp.Timing;
using Volo.Abp.Validation;

namespace AbpRuntimeTests;

[DependsOn(
    typeof(AbpAuthorizationModule),
    typeof(AbpTimingModule),
    typeof(AbpEventBusModule),
    typeof(AbpCachingModule),
    typeof(AbpValidationModule),
    typeof(AbpSettingsModule),
    typeof(AbpAutoMapperModule),
    typeof(AbpAutofacModule),
    typeof(AbpTestBaseModule)
)]
public class RuntimeTestModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpClockOptions>(options => options.Kind = DateTimeKind.Utc);

        context.Services.AddAutoMapperObjectMapper<RuntimeTestModule>();
        Configure<AbpAutoMapperOptions>(options => options.AddMaps<RuntimeTestModule>());

        // In-memory distributed cache so IDistributedCache<T> resolves without Redis.
        context.Services.AddDistributedMemoryCache();

        // Register the interceptor around the sample service so the dynamic-proxy test can
        // prove interception actually runs (a compile-smoke cannot reach this).
        context.Services.OnRegistered(registration =>
        {
            if (typeof(IInterceptedService).IsAssignableFrom(registration.ImplementationType))
            {
                registration.Interceptors.TryAdd<CountingInterceptor>();
            }
        });
    }
}

public class RuntimePermissionDefinitionProvider : PermissionDefinitionProvider
{
    public override void Define(IPermissionDefinitionContext context)
    {
        var group = context.AddGroup("RuntimeTests");
        group.AddPermission("RuntimeTests.DoThing");
    }
}

public class RuntimeSettingDefinitionProvider : SettingDefinitionProvider
{
    public override void Define(ISettingDefinitionContext context)
    {
        context.Add(new SettingDefinition("Runtime.Greeting", defaultValue: "hello"));
    }
}

public interface IInterceptedService
{
    Task<int> DoAsync();
}

public class InterceptedService : IInterceptedService, ITransientDependency
{
    public virtual Task<int> DoAsync() => Task.FromResult(42);
}

public class CountingInterceptor : AbpInterceptor, ITransientDependency
{
    public static int Count;

    public override async Task InterceptAsync(IAbpMethodInvocation invocation)
    {
        Interlocked.Increment(ref Count);
        await invocation.ProceedAsync();
    }
}

public class PingEto
{
    public string Message { get; set; } = string.Empty;
}

public class PingEventHandler : ILocalEventHandler<PingEto>, ITransientDependency
{
    public static int Count;

    public Task HandleEventAsync(PingEto eventData)
    {
        Interlocked.Increment(ref Count);
        return Task.CompletedTask;
    }
}

public interface IGuardedService
{
    Task<string> DoGuardedThingAsync();
}

// The [Authorize] on the method makes AbpAuthorizationModule auto-attach its
// AuthorizationInterceptor (see AuthorizationInterceptorRegistrar.ShouldIntercept),
// so calling this service actually runs the authorization pipeline.
public class GuardedService : IGuardedService, ITransientDependency
{
    [Authorize("RuntimeTests.DoThing")]
    public virtual Task<string> DoGuardedThingAsync() => Task.FromResult("done");
}

public class SampleCacheItem
{
    public string Value { get; set; } = string.Empty;
}

public class CreateWidgetInput
{
    [Required]
    public string? Name { get; set; }
}

public class MapSource
{
    public string Name { get; set; } = string.Empty;
}

public class MapDest
{
    public string Name { get; set; } = string.Empty;
}

public class RuntimeMapProfile : Profile
{
    public RuntimeMapProfile()
    {
        CreateMap<MapSource, MapDest>();
    }
}

public interface IValidatedService
{
    Task DoAsync(CreateWidgetInput input);
}

// IValidationEnabled makes AbpValidationModule auto-attach the ValidationInterceptor,
// so an invalid argument throws before the method body runs.
public class ValidatedService : IValidatedService, IValidationEnabled, ITransientDependency
{
    public virtual Task DoAsync(CreateWidgetInput input) => Task.CompletedTask;
}
