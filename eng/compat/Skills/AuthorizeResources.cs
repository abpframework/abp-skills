using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.Authorization.Permissions.Resources;
using Volo.Abp.MultiTenancy;

namespace AbpSkillsCompat.Skills;

internal static class AuthorizeResources
{
    internal static void DefineResourcePermission(IPermissionDefinitionContext context)
    {
        PermissionDefinition permission = context.AddResourcePermission(
            "BookStore.Books.Edit",
            "Acme.BookStore.Books.Book",
            "BookStore.Books.ManageResourcePermissions",
            displayName: null,
            multiTenancySide: MultiTenancySides.Both,
            isEnabled: true);

        _ = permission;
    }

    internal static async Task CheckAsync(IResourcePermissionChecker checker)
    {
        bool granted = await checker.IsGrantedAsync(
            "BookStore.Books.Edit",
            "Acme.BookStore.Books.Book",
            "some-resource-key");

        _ = granted;
    }

    internal static async Task RuleBasedAsync(IAuthorizationService authorizationService, object resource)
    {
        AuthorizationResult result = await authorizationService.AuthorizeAsync(resource, "BookStore.Books.Edit");
        bool ok = await authorizationService.IsGrantedAsync(resource, "BookStore.Books.Edit");
        _ = result;
        _ = ok;
    }
}
