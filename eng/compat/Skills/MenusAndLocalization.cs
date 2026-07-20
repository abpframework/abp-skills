// Compile-smoke for skill: abp-ui/menus-and-localization
// Exercises IMenuContributor + MenuConfigurationContext + ApplicationMenuItem +
// StandardMenus, AbpNavigationOptions, [LocalizationResourceName], AbpLocalizationOptions
// (Resources.Add<T>(...).AddVirtualJson) and IStringLocalizer<TResource>.
using System.Threading.Tasks;
using Microsoft.Extensions.Localization;
using Volo.Abp.Localization;
using Volo.Abp.UI.Navigation;

namespace AbpSkillsCompat.Skills;

[LocalizationResourceName("MyProject")]
internal sealed class MyProjectResource
{
}

internal sealed class MyProjectMenuContributor : IMenuContributor
{
    public async Task ConfigureMenuAsync(MenuConfigurationContext context)
    {
        if (context.Menu.Name != StandardMenus.Main)
        {
            return;
        }

        var l = context.GetLocalizer<MyProjectResource>();

        context.Menu.AddItem(
            new ApplicationMenuItem(
                name: "MyProject.Books",
                displayName: l["Menu:Books"],
                url: "/books",
                icon: "fas fa-book",
                order: 2));

        await Task.CompletedTask;
    }
}

internal static class MenusAndLocalization
{
    internal static void RegisterMenu(AbpNavigationOptions options)
    {
        options.MenuContributors.Add(new MyProjectMenuContributor());
    }

    internal static void RegisterResource(AbpLocalizationOptions options)
    {
        options.Resources
            .Add<MyProjectResource>("en")
            .AddVirtualJson("/Localization/MyProject");
    }

    internal static string Localize(IStringLocalizer<MyProjectResource> localizer)
    {
        return localizer["BookName"];
    }
}
