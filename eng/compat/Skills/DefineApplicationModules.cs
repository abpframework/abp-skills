// Compile-smoke for skill: abp-module-development/define-application-modules
// Exercises the AbpModule lifecycle, options helpers, and application factory.
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

internal sealed class SampleModule : AbpModule
{
    public override void PreConfigureServices(ServiceConfigurationContext context)
    {
        PreConfigure<SampleOptions>(o => o.Enabled = true);
    }

    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<SampleOptions>(o => o.Enabled = true);
        var preConfigured = context.Services.ExecutePreConfiguredActions<SampleOptions>();
    }

    public override void OnApplicationInitialization(ApplicationInitializationContext context)
    {
    }
}

internal sealed class SampleOptions
{
    public bool Enabled { get; set; }
}

internal static class DefineApplicationModules
{
    internal static async Task StartupApi(IServiceCollection services)
    {
        // internal service provider factory
        var app = await AbpApplicationFactory.CreateAsync<SampleModule>(services);
        // external service provider on a host IServiceCollection
        var external = await services.AddApplicationAsync<SampleModule>();
    }
}
