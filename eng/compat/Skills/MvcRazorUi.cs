// Compile-smoke for skill: abp-ui/mvc-razor-ui
// Exercises AbpPageModel (LocalizationResourceType, L, CheckPolicyAsync), AbpBundlingOptions
// (ScriptBundles.Configure + AddFiles, Mode/BundlingMode), and the AbpButtonType / AbpModalSize
// / AbpModalButtons tag-helper enums as C# types.
// Razor markup (abp-* tag helpers) and modal-manager JS in the skill are not compile-checked.
using System.Threading.Tasks;
using Volo.Abp.AspNetCore.Mvc.UI.Bootstrap.TagHelpers.Button;
using Volo.Abp.AspNetCore.Mvc.UI.Bootstrap.TagHelpers.Modal;
using Volo.Abp.AspNetCore.Mvc.UI.Bundling;
using Volo.Abp.AspNetCore.Mvc.UI.RazorPages;
using MyProjectResource = AbpSkillsCompat.Skills.MvcRazorUi;

namespace AbpSkillsCompat.Skills;

internal sealed class CreateModalModel : AbpPageModel
{
    public CreateModalModel()
    {
        LocalizationResourceType = typeof(MyProjectResource);
    }

    public async Task OnGetAsync()
    {
        var title = L["NewBook"];
        await CheckPolicyAsync("MyProject.Books.Create");
    }
}

internal static class MvcRazorUi
{
    internal static void ConfigureBundles(AbpBundlingOptions options)
    {
        options.Mode = BundlingMode.Auto;
        options.ScriptBundles.Configure("MyProject.Global", bundle =>
        {
            bundle.AddFiles("/global-scripts.js");
        });
    }

    internal static (AbpButtonType, AbpModalSize, AbpModalButtons) Enums()
    {
        return (AbpButtonType.Primary, AbpModalSize.Large, AbpModalButtons.Cancel | AbpModalButtons.Save);
    }
}
