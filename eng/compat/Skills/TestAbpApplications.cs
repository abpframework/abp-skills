// Compile-smoke for skill: abp-testing/test-abp-applications
// Exercises AbpIntegratedTest<TStartupModule>, GetRequiredService, WithUnitOfWork via
// IUnitOfWorkManager.Begin, ICurrentPrincipalAccessor.Change + AbpClaimTypes,
// ICurrentTenant.Change, IDataSeedContributor, and the [Authorize] DENY replacement path.
using System;
using System.Collections.Generic;
using System.Security.Claims;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Volo.Abp;
using Volo.Abp.Authorization;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Modularity;
using Volo.Abp.MultiTenancy;
using Volo.Abp.Security.Claims;
using Volo.Abp.Testing;
using Volo.Abp.Uow;
using Volo.Abp.Users;

namespace AbpSkillsCompat.Skills;

internal sealed class SampleTestModule : AbpModule
{
}

internal sealed class SampleTestDataSeedContributor : IDataSeedContributor, ITransientDependency
{
    public Task SeedAsync(DataSeedContext context)
    {
        var tenantId = context.TenantId;
        return Task.CompletedTask;
    }
}

internal sealed class DenyPermissionChecker : IPermissionChecker, ITransientDependency
{
    public Task<bool> IsGrantedAsync(string name) => Task.FromResult(false);
    public Task<bool> IsGrantedAsync(ClaimsPrincipal? claimsPrincipal, string name) => Task.FromResult(false);
    public Task<MultiplePermissionGrantResult> IsGrantedAsync(string[] names) => Task.FromResult(new MultiplePermissionGrantResult());
    public Task<MultiplePermissionGrantResult> IsGrantedAsync(ClaimsPrincipal? claimsPrincipal, string[] names) => Task.FromResult(new MultiplePermissionGrantResult());
}

internal sealed class SampleAppService_Tests : AbpIntegratedTest<SampleTestModule>
{
    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
    }

    protected override void AfterAddApplication(IServiceCollection services)
    {
        base.AfterAddApplication(services);

        // DENY-recovery path replaces ALL THREE authorization decision points the skill
        // documents (Microsoft IAuthorizationService, IAbpAuthorizationService, and
        // IMethodInvocationAuthorizationService), then a deterministic DENY permission checker.
        services.Replace(ServiceDescriptor.Transient<IAuthorizationService, AbpAuthorizationService>());
        services.Replace(ServiceDescriptor.Transient<IAbpAuthorizationService, AbpAuthorizationService>());
        services.Replace(ServiceDescriptor.Transient<IMethodInvocationAuthorizationService, MethodInvocationAuthorizationService>());
        services.Replace(ServiceDescriptor.Singleton<IPermissionChecker, DenyPermissionChecker>());

        // EF rollback path, in the order the skill documents: the template first applies
        // AddAlwaysDisableUnitOfWorkTransaction (registering AlwaysDisableTransactionsUnitOfWorkManager)...
        services.AddAlwaysDisableUnitOfWorkTransaction();

        // ...then the rollback-specific test base restores the real UnitOfWorkManager AFTER it,
        // so IsTransactional = true is honored. This Replace must come last to win.
        services.Replace(ServiceDescriptor.Singleton<IUnitOfWorkManager>(
            serviceProvider => serviceProvider.GetRequiredService<UnitOfWorkManager>()));
    }

    public async Task Exercise()
    {
        var uowManager = GetRequiredService<IUnitOfWorkManager>();
        var accessor = GetRequiredService<ICurrentPrincipalAccessor>();
        var currentUser = GetRequiredService<ICurrentUser>();
        var currentTenant = GetRequiredService<ICurrentTenant>();

        var identity = new ClaimsIdentity(
            new List<Claim>
            {
                new Claim(AbpClaimTypes.UserId, Guid.NewGuid().ToString()),
                new Claim(AbpClaimTypes.UserName, "test-user"),
                new Claim(AbpClaimTypes.Role, "admin"),
            },
            authenticationType: "Test");

        using (accessor.Change(new ClaimsPrincipal(identity)))
        using (currentTenant.Change(Guid.NewGuid()))
        {
            var id = currentUser.Id;
            using (var uow = uowManager.Begin(new AbpUnitOfWorkOptions { IsTransactional = true }))
            {
                await uow.CompleteAsync();
            }
        }
    }
}
