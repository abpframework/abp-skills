// Compile-smoke for skill: abp-ui/build-mvc-widgets
// Exercises the [Widget] attribute (RefreshUrl, AutoInitialize, ScriptFiles, StyleFiles,
// RequiresAuthentication, RequiredPolicies), a widget as an AbpViewComponent, and
// AbpWidgetOptions.Widgets.Add<TViewComponent>. The client-side abp.widgets / WidgetManager
// JavaScript in the skill is not compile-checked.
using Microsoft.AspNetCore.Mvc;
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.AspNetCore.Mvc.UI.Widgets;

namespace AbpSkillsCompat.Skills;

[Widget(
    RefreshUrl = "/Widgets/Counter/Refresh",
    AutoInitialize = true,
    ScriptFiles = new[] { "/widgets/counter/counter.js" },
    StyleFiles = new[] { "/widgets/counter/counter.css" },
    RequiresAuthentication = true,
    RequiredPolicies = new[] { "MyProject.Dashboard" })]
internal sealed class CounterWidgetViewComponent : AbpViewComponent
{
    public IViewComponentResult Invoke()
    {
        return View();
    }
}

internal static class BuildMvcWidgets
{
    internal static void Configure(AbpWidgetOptions options)
    {
        options.Widgets.Add<CounterWidgetViewComponent>();
    }
}
