using System.Reflection;
using Volo.Abp;
using Volo.Abp.AspNetCore.Mvc;

namespace AbpSkillsCompat.Skills;

[RemoteService(IsEnabled = true, IsMetadataEnabled = true)]
[IntegrationService]
internal class SampleIntegrationService
{
}

internal static class ExposeHttpApis
{
    internal static void ConfigureConventionalControllers(AbpAspNetCoreMvcOptions options, Assembly assembly)
    {
        options.ConventionalControllers.Create(assembly, setting =>
        {
            setting.RootPath = "app";
            setting.RemoteServiceName = "Default";
            setting.ApplicationServiceTypes = ApplicationServiceTypes.All;
        });

        options.ExposeIntegrationServices = true;
    }

    internal static void ServiceTypeFlags()
    {
        ApplicationServiceTypes all = ApplicationServiceTypes.All
                                      | ApplicationServiceTypes.ApplicationServices
                                      | ApplicationServiceTypes.IntegrationServices;
        _ = all;
    }
}
