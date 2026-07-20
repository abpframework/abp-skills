// Compile-smoke for skill: abp-multitenancy/configure-multi-tenancy
// Exercises ICurrentTenant.Change scopes, IDataFilter.Disable<IMultiTenant>,
// AbpMultiTenancyOptions, plus tenant resolution (AbpTenantResolveOptions / TenantKey /
// AddDomainTenantResolver / FallbackTenant), the tenant store (ITenantStore /
// TenantConfiguration), and a tenant-aware AsyncBackgroundJob.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Volo.Abp.AspNetCore.MultiTenancy;
using Volo.Abp.BackgroundJobs;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.MultiTenancy;

namespace AbpSkillsCompat.Skills;

internal class TenantOwnedProduct : AggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; set; }
}

internal sealed class MtRebuildCatalogArgs : IMultiTenant
{
    public Guid? TenantId { get; set; }
    public Guid CatalogId { get; set; }
}

// BackgroundJobExecuter enters CurrentTenant.Change(args.TenantId) for IMultiTenant args.
internal sealed class MtRebuildCatalogJob : AsyncBackgroundJob<MtRebuildCatalogArgs>
{
    public override Task ExecuteAsync(MtRebuildCatalogArgs args)
    {
        _ = args.CatalogId;
        return Task.CompletedTask;
    }
}

internal static class ConfigureMultiTenancy
{
    internal static void EnterScopes(ICurrentTenant currentTenant, Guid tenantId)
    {
        using (currentTenant.Change(tenantId, "acme"))
        {
            Guid? id = currentTenant.Id;
            string? name = currentTenant.Name;
            bool available = currentTenant.IsAvailable;
            _ = id;
            _ = name;
            _ = available;
        }

        using (currentTenant.Change(null))
        {
        }
    }

    internal static void DisableFilter(IDataFilter dataFilter)
    {
        using (dataFilter.Disable<IMultiTenant>())
        {
        }
    }

    internal static void ConfigureOptions(AbpMultiTenancyOptions options)
    {
        options.IsEnabled = true;
    }

    // Tenant resolution: domain resolver, custom contributors, and a fallback tenant.
    internal static void ConfigureResolvers(AbpTenantResolveOptions options)
    {
        options.AddDomainTenantResolver("{0}.mydomain.com");

        List<ITenantResolveContributor> resolvers = options.TenantResolvers;
        _ = resolvers.Count;

        options.FallbackTenant = "default";
    }

    // The query/route/header/cookie contributors read AbpAspNetCoreMultiTenancyOptions.TenantKey.
    internal static string ConfigureTenantKey(AbpAspNetCoreMultiTenancyOptions options)
    {
        options.TenantKey = "__tenant";
        return options.TenantKey;
    }

    // ITenantStore exposes TenantConfiguration for connection/edition resolution.
    internal static async Task<TenantConfiguration?> ResolveTenant(
        ITenantStore tenantStore,
        Guid tenantId)
    {
        IReadOnlyList<TenantConfiguration> tenants =
            await tenantStore.GetListAsync(includeDetails: true);

        TenantConfiguration? byId = await tenantStore.FindAsync(tenantId);
        TenantConfiguration? byName = await tenantStore.FindAsync("acme");

        foreach (var tenant in tenants)
        {
            Guid id = tenant.Id;
            string name = tenant.Name;
            bool active = tenant.IsActive;
            _ = (id, name, active);
        }

        return byId ?? byName;
    }

    internal static async Task<string> EnqueueTenantJob(
        IBackgroundJobManager backgroundJobManager,
        ICurrentTenant currentTenant,
        Guid catalogId)
    {
        return await backgroundJobManager.EnqueueAsync(
            new MtRebuildCatalogArgs
            {
                TenantId = currentTenant.Id,
                CatalogId = catalogId
            });
    }
}
