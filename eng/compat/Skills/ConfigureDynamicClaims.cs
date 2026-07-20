using System.Threading.Tasks;
using Volo.Abp.AspNetCore.Authentication.JwtBearer.DynamicClaims;
using Volo.Abp.Security.Claims;

namespace AbpSkillsCompat.Skills;

internal class SampleDynamicClaimsContributor : IAbpDynamicClaimsPrincipalContributor
{
    public Task ContributeAsync(AbpClaimsPrincipalContributorContext context)
    {
        return Task.CompletedTask;
    }
}

internal static class ConfigureDynamicClaims
{
    internal static void ConfigureFactory(AbpClaimsPrincipalFactoryOptions options)
    {
        options.IsDynamicClaimsEnabled = true;
        options.IsRemoteRefreshEnabled = true;
        options.RemoteRefreshUrl = "https://localhost:44300/api/account/dynamic-claims/refresh";
        options.DynamicClaims.Add(AbpClaimTypes.Role);
        _ = options.ClaimsMap;
        _ = options.DynamicContributors;
    }

    internal static void ConfigureWebRemote(WebRemoteDynamicClaimsPrincipalContributorOptions options)
    {
        options.IsEnabled = true;
        options.AuthenticationScheme = "Bearer";
    }

    internal static async Task RefreshAsync(IAbpClaimsPrincipalFactory factory)
    {
        var principal = await factory.CreateDynamicAsync(null);
        _ = principal;
    }
}
