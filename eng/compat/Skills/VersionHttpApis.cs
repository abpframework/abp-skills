// Compile-smoke for skill: abp-api/version-http-apis
// Exercises the ABP surface: AddAbpApiVersioning; the ConfigureAbp extension that wires
// per-assembly ConventionalControllerSetting.ApiVersions into MvcApiVersioningOptions; and
// ICurrentApiVersionInfo / ApiVersionInfo / ParameterBindingSources for runtime version
// selection. The ASP.NET API Versioning library types the skill labels as non-ABP
// (MvcApiVersioningOptions itself, ApiVersion) are not smoked beyond what ConfigureAbp needs.
using System;
using Asp.Versioning;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.Http.Client.ClientProxying;
using Volo.Abp.Http.ProxyScripting.Generators;

namespace AbpSkillsCompat.Skills;

internal static class VersionHttpApis
{
    internal static void Register(IServiceCollection services)
    {
        services.AddAbpApiVersioning();
    }

    internal static void WireConventionalControllerVersions(
        MvcApiVersioningOptions options, AbpAspNetCoreMvcOptions mvcOptions)
    {
        options.ConfigureAbp(mvcOptions);
    }

    internal static IDisposable SwitchVersion(ICurrentApiVersionInfo current)
    {
        return current.Change(new ApiVersionInfo(ParameterBindingSources.Query, "2.0"));
    }
}
