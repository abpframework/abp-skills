// Compile-smoke for skill: abp-ui/extend-application-shell (MVC surface)
// Exercises AbpLayoutHookOptions.Add with the LayoutHooks constants, a global toolbar via
// IToolbarContributor + StandardToolbars.Main adding a ToolbarItem gated by the
// RequirePermissions extension, the MVC IPageLayout header surface, and branding via a
// DefaultBrandingProvider override. The Blazor layout-hook/toolbar Razor components and
// MVC view components in the skill are not compile-checked.
using System.Threading.Tasks;
using Volo.Abp.AspNetCore.Mvc.UI.Layout;
using Volo.Abp.AspNetCore.Mvc.UI.Theme.Shared.Toolbars;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Ui.Branding;
using Volo.Abp.Ui.LayoutHooks;

namespace AbpSkillsCompat.Skills;

internal static class ExtendApplicationShell
{
    internal static void AddLayoutHooks(AbpLayoutHookOptions options)
    {
        options.Add(LayoutHooks.Head.Last, typeof(object));
        options.Add(LayoutHooks.Body.First, typeof(object));
        options.Add(LayoutHooks.PageContent.First, typeof(object));
    }

    internal static void SetPageHeader(IPageLayout pageLayout)
    {
        pageLayout.Content.Title = "Book List";
        pageLayout.Content.BreadCrumb.Add("Books");
        pageLayout.Content.MenuItemName = "BookStore.Books";
    }
}

internal sealed class MainToolbarContributor : IToolbarContributor
{
    public Task ConfigureToolbarAsync(IToolbarConfigurationContext context)
    {
        if (context.Toolbar.Name == StandardToolbars.Main)
        {
            var item = new ToolbarItem(typeof(object));
            item.RequirePermissions("MyPermissionName");
            context.Toolbar.Items.Add(item);
        }

        return Task.CompletedTask;
    }
}

[Dependency(ReplaceServices = true)]
internal sealed class MyBrandingProvider : DefaultBrandingProvider
{
    public override string AppName => "My App";

    public override string? LogoUrl => "/images/logo.png";
}
