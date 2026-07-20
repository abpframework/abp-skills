using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

internal static class ReadConfiguration
{
    internal static void InModule(ServiceConfigurationContext context)
    {
        IConfiguration configuration = context.Configuration;
        string? endpoint = configuration["ExternalApi:Endpoint"];
    }

    internal static void FromServices(IServiceCollection services)
    {
        IConfiguration configuration = services.GetConfiguration();
        IConfiguration? orNull = services.GetConfigurationOrNull();
    }

    internal static void Bootstrap(string[] args)
    {
        IConfigurationRoot configuration = ConfigurationHelper.BuildConfiguration(
            new AbpConfigurationBuilderOptions
            {
                FileName = "appsettings",
                EnvironmentName = "Development",
                CommandLineArgs = args
            });
    }

    internal static void SecretsJson(IConfigurationBuilder builder)
    {
        builder.AddAppSettingsSecretsJson();
    }
}
