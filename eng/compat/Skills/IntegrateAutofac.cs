using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Volo.Abp;
using Volo.Abp.Autofac;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

[DependsOn(typeof(AbpAutofacModule))]
internal sealed class AutofacCompatModule : AbpModule
{
}

internal static class IntegrateAutofac
{
    internal static void HostBuilder(IHostBuilder hostBuilder)
    {
        hostBuilder.UseAutofac();
    }

    internal static void CreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac();
    }

    internal static void ContainerBuilder(IServiceCollection services)
    {
        var builder = services.GetContainerBuilder();
    }
}
