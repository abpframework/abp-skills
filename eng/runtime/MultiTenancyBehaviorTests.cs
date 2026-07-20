// DB-backed runtime test for the multi-tenant data filter: rows written under one tenant
// must be invisible to another tenant's queries, and visible again when the filter is off.
// A compile-smoke cannot prove the filter actually executes.
using System;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Autofac;
using Volo.Abp.Data;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.MultiTenancy;
using Volo.Abp.Testing;
using Volo.Abp.Uow;
using Xunit;

namespace AbpRuntimeTests;

public class MultiTenancyBehaviorTests : AbpIntegratedTest<EfCoreTestModule>
{
    private readonly IRepository<TenantWidget, Guid> _widgets;
    private readonly ICurrentTenant _currentTenant;
    private readonly IUnitOfWorkManager _uowManager;
    private readonly IDataFilter _dataFilter;

    public MultiTenancyBehaviorTests()
    {
        _widgets = GetRequiredService<IRepository<TenantWidget, Guid>>();
        _currentTenant = GetRequiredService<ICurrentTenant>();
        _uowManager = GetRequiredService<IUnitOfWorkManager>();
        _dataFilter = GetRequiredService<IDataFilter>();
    }

    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac();
    }

    [Fact]
    public async Task Tenant_data_filter_isolates_rows_per_tenant()
    {
        var tenantA = Guid.NewGuid();
        var tenantB = Guid.NewGuid();

        // Insert one row under tenant A; ABP stamps TenantId from ICurrentTenant.
        await WithTenantAsync(tenantA, async () =>
            await _widgets.InsertAsync(new TenantWidget { Name = "a-widget" }, autoSave: true));

        // Tenant B can't see it.
        await WithTenantAsync(tenantB, async () => Assert.Empty(await _widgets.GetListAsync()));

        // Tenant A can.
        await WithTenantAsync(tenantA, async () =>
        {
            var list = await _widgets.GetListAsync();
            Assert.Single(list);
            Assert.Equal(tenantA, list[0].TenantId);
        });

        // With the filter disabled, the row is visible regardless of current tenant.
        await WithTenantAsync(tenantB, async () =>
        {
            using (_dataFilter.Disable<IMultiTenant>())
            {
                Assert.Single(await _widgets.GetListAsync());
            }
        });
    }

    private async Task WithTenantAsync(Guid tenantId, Func<Task> action)
    {
        using (_currentTenant.Change(tenantId))
        using (var uow = _uowManager.Begin(requiresNew: true))
        {
            await action();
            await uow.CompleteAsync();
        }
    }
}
