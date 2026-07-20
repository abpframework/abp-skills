using System;
using System.Security.Claims;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Volo.Abp.Authorization.Permissions;
using Volo.Abp.MultiTenancy;
using Volo.Abp.Security.Claims;
using Volo.Abp.Users;

namespace AbpSkillsCompat.Skills;

[Authorize("BookStore.Books")]
internal class SampleBookAppService
{
    [Authorize("BookStore.Books.Create")]
    internal virtual Task<string> CreateAsync() => Task.FromResult("book");
}

internal class SampleBookStorePermissionDefinitionProvider : PermissionDefinitionProvider
{
    public override void Define(IPermissionDefinitionContext context)
    {
        PermissionGroupDefinition group = context.AddGroup("BookStore", displayName: null);
        PermissionDefinition books = group.AddPermission("BookStore.Books", displayName: null, MultiTenancySides.Both);
        books.AddChild("BookStore.Books.Create", displayName: null);
    }
}

internal static class PermissionsAndAuthorization
{
    internal static async Task CheckAsync(IAuthorizationService authorizationService, IPermissionChecker permissionChecker)
    {
        bool byPolicy = await authorizationService.IsGrantedAsync("BookStore.Books");
        await authorizationService.CheckAsync("BookStore.Books.Delete");
        bool anyGranted = await authorizationService.IsGrantedAnyAsync("BookStore.Books.Create", "BookStore.Books.Edit");

        bool byChecker = await permissionChecker.IsGrantedAsync("BookStore.Books.Create");
        MultiplePermissionGrantResult batch =
            await permissionChecker.IsGrantedAsync(new[] { "BookStore.Books.Create", "BookStore.Books.Edit" });

        _ = byPolicy;
        _ = anyGranted;
        _ = byChecker;
        _ = batch;
    }

    internal static void ReadCurrentUser(ICurrentUser currentUser)
    {
        bool authenticated = currentUser.IsAuthenticated;
        Guid? id = currentUser.Id;
        bool admin = currentUser.IsInRole("admin");
        Claim? userIdClaim = currentUser.FindClaim(AbpClaimTypes.UserId);
        _ = authenticated;
        _ = id;
        _ = admin;
        _ = userIdClaim;
    }

    internal static void SwitchPrincipal(ICurrentPrincipalAccessor accessor, Guid userId)
    {
        // Pass an authentication type so ClaimsIdentity.IsAuthenticated is true.
        var replacement = new ClaimsPrincipal(
            new ClaimsIdentity(
                new[] { new Claim(AbpClaimTypes.UserId, userId.ToString()) },
                authenticationType: "Impersonation"));

        using (accessor.Change(replacement))
        {
            ClaimsPrincipal principal = accessor.Principal;
            _ = principal;
        }
    }
}
