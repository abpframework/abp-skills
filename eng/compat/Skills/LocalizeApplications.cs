// Compile-smoke for skill: abp-module-development/localize-applications
// Exercises AbpLocalizationOptions.Resources.Add<T> + AddVirtualJson / AddBaseTypes,
// [LocalizationResourceName], DefaultResourceType, and IStringLocalizer<T> consumption.
using System;
using Microsoft.Extensions.Localization;
using Volo.Abp.Localization;

namespace AbpSkillsCompat.Skills;

[LocalizationResourceName("Demo")]
internal sealed class DemoLocalizationResource
{
}

internal static class LocalizeApplications
{
    internal static void Configure(AbpLocalizationOptions options)
    {
        options.Resources
            .Add<DemoLocalizationResource>("en")
            .AddVirtualJson("/Localization/Demo")
            .AddBaseTypes(typeof(DemoLocalizationResource));

        options.DefaultResourceType = typeof(DemoLocalizationResource);
    }

    internal static string Use(IStringLocalizer<DemoLocalizationResource> localizer)
    {
        return localizer["HelloWorld"];
    }
}
