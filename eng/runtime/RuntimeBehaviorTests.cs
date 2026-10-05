// Executable ABP runtime behavior tests. Each boots the real ABP application (via
// AbpIntegratedTest) and asserts a runtime semantic that a compile-only smoke cannot prove.
using System;
using System.Security.Claims;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.Autofac;
using Volo.Abp.Caching;
using Volo.Abp.EventBus.Local;
using Volo.Abp.MultiTenancy;
using Volo.Abp.ObjectMapping;
using Volo.Abp.Settings;
using Volo.Abp.Validation;
using Volo.Abp.Security.Claims;
using Volo.Abp.Testing;
using Volo.Abp.Timing;
using Volo.Abp.Uow;
using Volo.Abp.Users;
using Xunit;

namespace AbpRuntimeTests;

public class RuntimeBehaviorTests : AbpIntegratedTest<RuntimeTestModule>
{
    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac();
    }

    [Fact]
    public async Task Permission_definition_provider_runs_and_registers_the_permission()
    {
        var manager = GetRequiredService<IPermissionDefinitionManager>();

        var permission = await manager.GetOrNullAsync("RuntimeTests.DoThing");

        Assert.NotNull(permission);
        Assert.Equal("RuntimeTests.DoThing", permission!.Name);
    }

    [Fact]
    public void Clock_normalizes_unspecified_datetime_to_utc()
    {
        var clock = GetRequiredService<IClock>();

        var normalized = clock.Normalize(new DateTime(2026, 1, 1, 12, 0, 0, DateTimeKind.Unspecified));

        Assert.Equal(DateTimeKind.Utc, normalized.Kind);
    }

    [Fact]
    public void Current_principal_change_flows_to_current_user()
    {
        var accessor = GetRequiredService<ICurrentPrincipalAccessor>();
        var currentUser = GetRequiredService<ICurrentUser>();
        var userId = Guid.NewGuid();

        var identity = new ClaimsIdentity(
            new[] { new Claim(AbpClaimTypes.UserId, userId.ToString()) },
            authenticationType: "Test");

        using (accessor.Change(new ClaimsPrincipal(identity)))
        {
            Assert.True(currentUser.IsAuthenticated);
            Assert.Equal(userId, currentUser.Id);
        }
    }

    [Fact]
    public async Task Registered_interceptor_runs_around_the_service_method()
    {
        CountingInterceptor.Count = 0;
        var service = GetRequiredService<IInterceptedService>();

        var result = await service.DoAsync();

        Assert.Equal(42, result);
        // The proxy actually wrapped the call — proves dynamic-proxy interception executes.
        Assert.True(CountingInterceptor.Count > 0);
    }

    [Fact]
    public async Task Handler_scope_is_disposed_before_its_after_commit_callback_runs()
    {
        AfterCommitHandler.CallbackResult = null;
        AfterCommitHandler.CallbackEntered = false;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            await eventBus.PublishAsync(new LazyInCallbackEto());
            await Assert.ThrowsAsync<ObjectDisposedException>(() => uow.CompleteAsync());
        }

        Assert.True(AfterCommitHandler.CallbackEntered);
        Assert.Null(AfterCommitHandler.CallbackResult);
    }

    [Fact]
    public async Task Value_resolved_inside_the_handler_is_usable_after_commit()
    {
        AfterCommitHandler.CallbackResult = null;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            await eventBus.PublishAsync(new LazyInHandlerEto());
            await uow.CompleteAsync();
        }

        Assert.Equal("probe", AfterCommitHandler.CallbackResult);
    }

    [Fact]
    public async Task Service_captured_in_the_handler_is_disposed_before_the_callback_runs()
    {
        DisposableAfterCommitHandler.CallbackSawDisposed = null;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            await eventBus.PublishAsync(new ServiceInCallbackEto());
            await uow.CompleteAsync();
        }

        Assert.True(DisposableAfterCommitHandler.CallbackSawDisposed);
    }

    [Fact]
    public async Task Callback_can_resolve_services_from_a_new_scope()
    {
        DisposableAfterCommitHandler.CallbackSawDisposed = null;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            await eventBus.PublishAsync(new NewScopeInCallbackEto());
            await uow.CompleteAsync();
        }

        Assert.False(DisposableAfterCommitHandler.CallbackSawDisposed);
    }

    [Fact]
    public void Lazy_dependency_is_built_only_when_a_method_needs_it()
    {
        HeavyDependency.Constructed = 0;
        var holder = GetRequiredService<LazyHolder>();

        holder.Light();
        Assert.Equal(0, HeavyDependency.Constructed);

        holder.UseHeavy();
        holder.UseHeavy();
        Assert.Equal(1, HeavyDependency.Constructed);
    }

    [Fact]
    public void Injected_enumerable_builds_every_implementation_with_its_holder()
    {
        CsvReportPlugin.Constructed = 0;
        PdfReportPlugin.Constructed = 0;

        GetRequiredService<EagerPluginHost>();

        Assert.Equal(1, CsvReportPlugin.Constructed);
        Assert.Equal(1, PdfReportPlugin.Constructed);
    }

    [Fact]
    public void Lazy_enumerable_defers_building_the_implementations()
    {
        CsvReportPlugin.Constructed = 0;
        PdfReportPlugin.Constructed = 0;

        var host = GetRequiredService<LazyPluginHost>();
        Assert.Equal(0, CsvReportPlugin.Constructed + PdfReportPlugin.Constructed);

        Assert.Equal(2, host.Count());
        Assert.Equal(1, CsvReportPlugin.Constructed);
        Assert.Equal(1, PdfReportPlugin.Constructed);
    }

    [Fact]
    public async Task Completed_callback_runs_after_the_handler_scope_ends_and_the_transaction_commits()
    {
        AfterCommitOrder.Steps.Clear();
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            uow.AddTransactionApi("recording", new RecordingTransactionApi());
            await eventBus.PublishAsync(new OrderEto());
            await uow.CompleteAsync();
        }

        Assert.Equal(
            new[] { "handler returned", "handler scope disposed", "commit", "callback" },
            AfterCommitOrder.Steps);
    }

    [Fact]
    public async Task Completed_callback_runs_in_the_tenant_active_at_completion_until_it_changes_back()
    {
        var tenantId = Guid.NewGuid();
        var publisherTenantId = Guid.NewGuid();
        OrderAndTenantHandler.HandlerTenant = null;
        OrderAndTenantHandler.CallbackTenant = Guid.Empty;
        OrderAndTenantHandler.RestoredCallbackTenant = null;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var eventBus = GetRequiredService<ILocalEventBus>();
        var currentTenant = GetRequiredService<ICurrentTenant>();
        Assert.Null(currentTenant.Id);

        using (var uow = unitOfWorkManager.Begin(requiresNew: true))
        {
            using (currentTenant.Change(publisherTenantId))
            {
                await eventBus.PublishAsync(new TenantEto { TenantId = tenantId });
            }

            await uow.CompleteAsync();
        }

        Assert.Equal(tenantId, OrderAndTenantHandler.HandlerTenant);
        Assert.Null(OrderAndTenantHandler.CallbackTenant);
        Assert.Equal(tenantId, OrderAndTenantHandler.RestoredCallbackTenant);
    }

    [Fact]
    public async Task Completed_callback_stays_inside_a_scope_and_tenant_that_are_still_active()
    {
        var tenantId = Guid.NewGuid();
        bool? probeDisposed = null;
        Guid? callbackTenant = null;
        var unitOfWorkManager = GetRequiredService<IUnitOfWorkManager>();
        var currentTenant = GetRequiredService<ICurrentTenant>();

        using (var scope = GetRequiredService<IServiceScopeFactory>().CreateScope())
        using (currentTenant.Change(tenantId))
        {
            var probe = scope.ServiceProvider.GetRequiredService<DisposableProbe>();
            using (var uow = unitOfWorkManager.Begin(requiresNew: true))
            {
                uow.OnCompleted(() =>
                {
                    probeDisposed = probe.IsDisposed;
                    callbackTenant = currentTenant.Id;
                    return Task.CompletedTask;
                });
                await uow.CompleteAsync();
            }
        }

        Assert.False(probeDisposed);
        Assert.Equal(tenantId, callbackTenant);
    }

    [Fact]
    public void Lazy_dependency_is_cached_per_holder()
    {
        HeavyDependency.Constructed = 0;

        GetRequiredService<LazyHolder>().UseHeavy();
        GetRequiredService<LazyHolder>().UseHeavy();

        Assert.Equal(2, HeavyDependency.Constructed);
    }

    [Fact]
    public async Task Local_event_is_delivered_to_its_handler()
    {
        PingEventHandler.Count = 0;
        var eventBus = GetRequiredService<ILocalEventBus>();

        await eventBus.PublishAsync(new PingEto { Message = "hi" });

        Assert.True(PingEventHandler.Count > 0);
    }

    [Fact]
    public async Task Distributed_cache_round_trips_a_typed_item()
    {
        var cache = GetRequiredService<IDistributedCache<SampleCacheItem>>();

        await cache.SetAsync("k1", new SampleCacheItem { Value = "v1" });
        var cached = await cache.GetAsync("k1");

        Assert.NotNull(cached);
        Assert.Equal("v1", cached!.Value);
    }

    [Fact]
    public async Task Validation_interceptor_rejects_an_invalid_argument()
    {
        var service = GetRequiredService<IValidatedService>();

        // Name is [Required]; a null one must be blocked by the validation interceptor.
        await Assert.ThrowsAsync<AbpValidationException>(
            () => service.DoAsync(new CreateWidgetInput { Name = null }));
    }

    [Fact]
    public async Task Setting_provider_returns_the_defined_default_value()
    {
        var settings = GetRequiredService<ISettingProvider>();

        Assert.Equal("hello", await settings.GetOrNullAsync("Runtime.Greeting"));
    }

    [Fact]
    public void Object_mapper_maps_through_the_registered_profile()
    {
        var mapper = GetRequiredService<IObjectMapper>();

        var dest = mapper.Map<MapSource, MapDest>(new MapSource { Name = "x" });

        Assert.Equal("x", dest.Name);
    }
}
