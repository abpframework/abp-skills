// Compile-smoke for skill: abp-module-development/create-plugin-modules
// Exercises AbpApplicationCreationOptions.PlugInSources with AddFolder/AddFiles/AddTypes,
// FolderPlugInSource, and an AbpModule-derived plug-in.
using System.IO;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Modularity;
using Volo.Abp.Modularity.PlugIns;

namespace AbpSkillsCompat.Skills;

internal sealed class SamplePlugInModule : AbpModule
{
    public override void OnApplicationInitialization(ApplicationInitializationContext context)
    {
        var service = context.ServiceProvider.GetRequiredService<SamplePlugInService>();
        service.Initialize();
    }
}

internal sealed class SamplePlugInService : ITransientDependency
{
    public void Initialize()
    {
    }
}

internal static class CreatePluginModules
{
    internal static void ConfigurePlugInSources(AbpApplicationCreationOptions options)
    {
        options.PlugInSources.AddFolder(@"D:\Temp\MyPlugIns");
        options.PlugInSources.AddFolder(@"D:\Temp\MyPlugIns", SearchOption.AllDirectories);
        options.PlugInSources.AddFiles(@"D:\Temp\MyPlugIns\MyPlugIn.dll");
        options.PlugInSources.AddTypes(typeof(SamplePlugInModule));
        options.PlugInSources.Add(new FolderPlugInSource(@"D:\Temp\MyPlugIns"));
    }
}
