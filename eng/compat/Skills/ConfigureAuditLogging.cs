using System;
using System.IO;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Auditing;
using Volo.Abp.Data;
using Volo.Abp.AspNetCore.Auditing;
using Volo.Abp.Domain.Entities;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureAuditLogging
{
    internal static void Options(AbpAuditingOptions options)
    {
        options.IsEnabled = true;
        options.IsEnabledForGetRequests = false;
        options.HideErrors = true;
        options.AlwaysLogOnException = true;
        options.IgnoredTypes.Add(typeof(Stream));

        options.EntityHistorySelectors.AddAllEntities();
        options.EntityHistorySelectors.Add(
            new NamedTypeSelector("MySelector", type => typeof(IEntity).IsAssignableFrom(type)));

        options.Contributors.Add(new MyAuditContributor());
    }

    internal static void AspNetCoreOptions(AbpAspNetCoreAuditingOptions options)
    {
        options.IgnoredUrls.Add("/health");
    }

    internal static async Task Manager(IAuditingManager manager)
    {
        IAuditLogScope? current = manager.Current;
        using (var handle = manager.BeginScope())
        {
            await handle.SaveAsync();
        }
    }
}

[Audited]
internal sealed class MyAuditedEntity : Entity<Guid>
{
    public string Name { get; set; } = string.Empty;

    [DisableAuditing]
    public string Secret { get; set; } = string.Empty;
}

internal sealed class MyAuditContributor : AuditLogContributor
{
    public override void PreContribute(AuditLogContributionContext context)
    {
        context.AuditInfo.SetProperty("K", "V");
    }
}
