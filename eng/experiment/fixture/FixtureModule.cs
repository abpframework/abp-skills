using Volo.Abp.Autofac;
using Volo.Abp.Modularity;
using Volo.Abp.Application;

namespace Acme.Fixture;

[DependsOn(
    typeof(AbpAutofacModule),
    typeof(AbpDddApplicationModule))]
public class FixtureModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        // Register application services and configure options here.
    }
}
