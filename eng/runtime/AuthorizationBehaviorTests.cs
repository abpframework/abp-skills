// Runtime behavior tests for the [Authorize] pipeline: a compile-smoke proves the
// attribute/types exist, but only a booted app proves the authorization interceptor
// actually blocks a denied call and lets an allowed one through.
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.Authorization;
using Volo.Abp.Autofac;
using Volo.Abp.Testing;
using Xunit;

namespace AbpRuntimeTests;

public class AuthorizationDenyTests : AbpIntegratedTest<RuntimeTestModule>
{
    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac(); // required so the [Authorize] interceptor proxy is created
    }

    [Fact]
    public async Task Authorize_denies_the_call_when_the_permission_is_not_granted()
    {
        var service = GetRequiredService<IGuardedService>();

        // Anonymous user, permission not granted -> the interceptor must throw.
        // (If the interceptor never attached, no exception would be thrown and this fails.)
        await Assert.ThrowsAsync<AbpAuthorizationException>(() => service.DoGuardedThingAsync());
    }
}

public class AuthorizationAllowTests : AbpIntegratedTest<RuntimeTestModule>
{
    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac();
    }

    protected override void AfterAddApplication(IServiceCollection services)
    {
        base.AfterAddApplication(services);
        services.AddAlwaysAllowAuthorization(); // replace the checker so the guarded call passes
    }

    [Fact]
    public async Task Authorize_allows_the_call_under_always_allow()
    {
        var service = GetRequiredService<IGuardedService>();

        var result = await service.DoGuardedThingAsync();

        Assert.Equal("done", result);
    }
}
