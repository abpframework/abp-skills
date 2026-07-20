using System.Threading.Tasks;
using Volo.Abp.AspNetCore.Mvc.ApplicationConfigurations;
using Volo.Abp.Data;

namespace AbpSkillsCompat.Skills;

internal class DeploymentVersionContributor : IApplicationConfigurationContributor
{
    public Task ContributeAsync(ApplicationConfigurationContributorContext context)
    {
        ApplicationConfigurationDto config = context.ApplicationConfiguration;
        config.SetProperty("deploymentVersion", "1.0.0");
        _ = context.ServiceProvider;
        return Task.CompletedTask;
    }
}

internal static class UseAbpStandardEndpoints
{
    internal static void RegisterContributor(AbpApplicationConfigurationOptions options)
    {
        options.Contributors.Add(new DeploymentVersionContributor());
    }

    internal static void RequestOptions()
    {
        ApplicationConfigurationRequestOptions configRequest = new ApplicationConfigurationRequestOptions
        {
            IncludeLocalizationResources = false
        };

        ApplicationLocalizationRequestDto locRequest = new ApplicationLocalizationRequestDto
        {
            CultureName = "en",
            OnlyDynamics = true
        };

        _ = configRequest.IncludeLocalizationResources;
        _ = locRequest.CultureName;
        _ = locRequest.OnlyDynamics;
    }
}
