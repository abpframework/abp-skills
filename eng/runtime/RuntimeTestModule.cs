// Startup module for the runtime behavior tests: the minimal ABP application under test.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
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
using Volo.Abp.MultiTenancy;
using Volo.Abp.Settings;
using Volo.Abp.Timing;
using Volo.Abp.Uow;
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

public class AfterCommitProbe : ITransientDependency
{
    public string Read() => "probe";
}

public class LazyInCallbackEto
{
}

public class LazyInHandlerEto
{
}

// Both handlers register work for after the unit of work commits. ABP disposes a local event
// handler's scope as soon as the handler returns, before that commit, so the Lazy<T> may only be
// read while the handler is still running.
public class AfterCommitHandler :
    ILocalEventHandler<LazyInCallbackEto>,
    ILocalEventHandler<LazyInHandlerEto>,
    ITransientDependency
{
    public static string? CallbackResult;
    public static bool CallbackEntered;

    private readonly IUnitOfWorkManager _unitOfWorkManager;
    private readonly Lazy<AfterCommitProbe> _probe;

    public AfterCommitHandler(IUnitOfWorkManager unitOfWorkManager, Lazy<AfterCommitProbe> probe)
    {
        _unitOfWorkManager = unitOfWorkManager;
        _probe = probe;
    }

    public Task HandleEventAsync(LazyInCallbackEto eventData)
    {
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            CallbackEntered = true;
            CallbackResult = _probe.Value.Read();
            return Task.CompletedTask;
        });
        return Task.CompletedTask;
    }

    public Task HandleEventAsync(LazyInHandlerEto eventData)
    {
        var result = _probe.Value.Read();
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            CallbackResult = result;
            return Task.CompletedTask;
        });
        return Task.CompletedTask;
    }
}

public class HeavyDependency : ITransientDependency
{
    public static int Constructed;

    public HeavyDependency()
    {
        Interlocked.Increment(ref Constructed);
    }

    public string Render() => "rendered";
}

public class LazyHolder : ITransientDependency
{
    private readonly Lazy<HeavyDependency> _heavy;

    public LazyHolder(Lazy<HeavyDependency> heavy)
    {
        _heavy = heavy;
    }

    public string Light() => "light";

    public string UseHeavy() => _heavy.Value.Render();
}

public interface IReportPlugin
{
}

public class CsvReportPlugin : IReportPlugin, ITransientDependency
{
    public static int Constructed;

    public CsvReportPlugin()
    {
        Interlocked.Increment(ref Constructed);
    }
}

public class PdfReportPlugin : IReportPlugin, ITransientDependency
{
    public static int Constructed;

    public PdfReportPlugin()
    {
        Interlocked.Increment(ref Constructed);
    }
}

public class EagerPluginHost : ITransientDependency
{
    private readonly IEnumerable<IReportPlugin> _plugins;

    public EagerPluginHost(IEnumerable<IReportPlugin> plugins)
    {
        _plugins = plugins;
    }

    public int Count() => _plugins.Count();
}

public class LazyPluginHost : ITransientDependency
{
    private readonly Lazy<IEnumerable<IReportPlugin>> _plugins;

    public LazyPluginHost(Lazy<IEnumerable<IReportPlugin>> plugins)
    {
        _plugins = plugins;
    }

    public int Count() => _plugins.Value.Count();
}

public class DisposableProbe : ITransientDependency, IDisposable
{
    public bool IsDisposed { get; private set; }

    public void Dispose()
    {
        IsDisposed = true;
    }
}

public class ServiceInCallbackEto
{
}

public class NewScopeInCallbackEto
{
}

public class DisposableAfterCommitHandler :
    ILocalEventHandler<ServiceInCallbackEto>,
    ILocalEventHandler<NewScopeInCallbackEto>,
    ITransientDependency
{
    public static bool? CallbackSawDisposed;

    private readonly IUnitOfWorkManager _unitOfWorkManager;
    private readonly Lazy<DisposableProbe> _probe;
    private readonly IServiceScopeFactory _scopeFactory;

    public DisposableAfterCommitHandler(
        IUnitOfWorkManager unitOfWorkManager,
        Lazy<DisposableProbe> probe,
        IServiceScopeFactory scopeFactory)
    {
        _unitOfWorkManager = unitOfWorkManager;
        _probe = probe;
        _scopeFactory = scopeFactory;
    }

    public Task HandleEventAsync(ServiceInCallbackEto eventData)
    {
        var probe = _probe.Value;
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            CallbackSawDisposed = probe.IsDisposed;
            return Task.CompletedTask;
        });
        return Task.CompletedTask;
    }

    public Task HandleEventAsync(NewScopeInCallbackEto eventData)
    {
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            using var scope = _scopeFactory.CreateScope();
            CallbackSawDisposed = scope.ServiceProvider.GetRequiredService<DisposableProbe>().IsDisposed;
            return Task.CompletedTask;
        });
        return Task.CompletedTask;
    }
}

public static class AfterCommitOrder
{
    public static readonly List<string> Steps = new();
}

public class RecordingTransactionApi : ITransactionApi
{
    public Task CommitAsync(CancellationToken cancellationToken = default)
    {
        AfterCommitOrder.Steps.Add("commit");
        return Task.CompletedTask;
    }

    public void Dispose()
    {
    }
}

public class OrderProbe : ITransientDependency, IDisposable
{
    public void Dispose()
    {
        AfterCommitOrder.Steps.Add("handler scope disposed");
    }
}

public class OrderEto
{
}

public class TenantEto : IMultiTenant
{
    public Guid? TenantId { get; set; }
}

public class OrderAndTenantHandler :
    ILocalEventHandler<OrderEto>,
    ILocalEventHandler<TenantEto>,
    ITransientDependency
{
    public static Guid? HandlerTenant;
    public static Guid? CallbackTenant;
    public static Guid? RestoredCallbackTenant;

    private readonly IUnitOfWorkManager _unitOfWorkManager;
    private readonly OrderProbe _probe;
    private readonly ICurrentTenant _currentTenant;
    private readonly IServiceScopeFactory _scopeFactory;

    public OrderAndTenantHandler(
        IUnitOfWorkManager unitOfWorkManager,
        OrderProbe probe,
        ICurrentTenant currentTenant,
        IServiceScopeFactory scopeFactory)
    {
        _unitOfWorkManager = unitOfWorkManager;
        _probe = probe;
        _currentTenant = currentTenant;
        _scopeFactory = scopeFactory;
    }

    public Task HandleEventAsync(OrderEto eventData)
    {
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            AfterCommitOrder.Steps.Add("callback");
            return Task.CompletedTask;
        });
        AfterCommitOrder.Steps.Add("handler returned");
        return Task.CompletedTask;
    }

    public Task HandleEventAsync(TenantEto eventData)
    {
        HandlerTenant = _currentTenant.Id;
        var tenantId = _currentTenant.Id;
        _unitOfWorkManager.Current!.OnCompleted(() =>
        {
            using var scope = _scopeFactory.CreateScope();
            var currentTenant = scope.ServiceProvider.GetRequiredService<ICurrentTenant>();
            CallbackTenant = currentTenant.Id;
            using (currentTenant.Change(tenantId))
            {
                RestoredCallbackTenant = currentTenant.Id;
            }

            return Task.CompletedTask;
        });
        return Task.CompletedTask;
    }
}
