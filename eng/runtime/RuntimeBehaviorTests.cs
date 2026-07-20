// Executable ABP runtime behavior tests. Each boots the real ABP application (via
// AbpIntegratedTest) and asserts a runtime semantic that a compile-only smoke cannot prove.
using System;
using System.Security.Claims;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.Autofac;
using Volo.Abp.Caching;
using Volo.Abp.EventBus.Local;
using Volo.Abp.ObjectMapping;
using Volo.Abp.Settings;
using Volo.Abp.Validation;
using Volo.Abp.Security.Claims;
using Volo.Abp.Testing;
using Volo.Abp.Timing;
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
