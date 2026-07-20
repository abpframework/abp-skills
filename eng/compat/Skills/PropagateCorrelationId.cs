using System;
using Microsoft.AspNetCore.Builder;
using Volo.Abp;
using Volo.Abp.Tracing;

namespace AbpSkillsCompat.Skills;

internal static class PropagateCorrelationId
{
    internal static void Middleware(ApplicationInitializationContext context)
    {
        IApplicationBuilder app = context.GetApplicationBuilder();
        app.UseCorrelationId();
    }

    internal static void Options(AbpCorrelationIdOptions options)
    {
        options.HttpHeaderName = "X-Correlation-Id";
        options.SetResponseHeader = true;
    }

    internal static void Provider(ICorrelationIdProvider provider)
    {
        string? current = provider.Get();
        using (IDisposable scope = provider.Change("id"))
        {
        }
    }
}
