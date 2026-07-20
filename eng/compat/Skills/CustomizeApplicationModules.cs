// Compile-smoke for skill: abp-module-development/customize-application-modules
// Exercises ObjectExtensionManager entity/DTO extension, and service replacement via
// [Dependency(ReplaceServices)] + [ExposeServices] + ServiceCollection.Replace.
using System.ComponentModel.DataAnnotations;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Modularity;
using Volo.Abp.ObjectExtending;

namespace AbpSkillsCompat.Skills;

internal interface ICustomizableModuleService
{
    void Run();
}

internal class DefaultCustomizableModuleService : ICustomizableModuleService, ITransientDependency
{
    public virtual void Run()
    {
    }
}

[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(ICustomizableModuleService), typeof(DefaultCustomizableModuleService))]
internal sealed class MyCustomizableModuleService : DefaultCustomizableModuleService
{
    public override void Run()
    {
        base.Run();
    }
}

internal sealed class CustomizeModulesModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        context.Services.Replace(
            ServiceDescriptor.Transient<ICustomizableModuleService, MyCustomizableModuleService>());
    }
}

internal sealed class CustomizableEntity : ExtensibleObject, IHasExtraProperties
{
}

internal sealed class CustomizableEntityDto : ExtensibleObject, IHasExtraProperties
{
}

internal static class CustomizeApplicationModules
{
    internal static void ConfigureExtraProperties()
    {
        ObjectExtensionManager.Instance
            .AddOrUpdateProperty<CustomizableEntity, string>(
                "SocialSecurityNumber",
                property =>
                {
                    property.Attributes.Add(new RequiredAttribute());
                    property.Attributes.Add(new StringLengthAttribute(64) { MinimumLength = 4 });
                });

        // Extra properties are not exposed on DTOs automatically — declare explicitly.
        ObjectExtensionManager.Instance
            .AddOrUpdateProperty<CustomizableEntityDto, string>(
                "SocialSecurityNumber",
                options => options.CheckPairDefinitionOnMapping = false);
    }
}
