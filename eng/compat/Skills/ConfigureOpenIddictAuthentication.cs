using System;
using System.Security.Cryptography.X509Certificates;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using OpenIddict.Abstractions;
using OpenIddict.Server;
using OpenIddict.Server.AspNetCore;
using Volo.Abp.OpenIddict;
using Volo.Abp.OpenIddict.Tokens;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureOpenIddictAuthentication
{
    internal static void ConfigureAbpOptions(AbpOpenIddictAspNetCoreOptions options)
    {
        options.AddDevelopmentEncryptionAndSigningCertificate = false;
        options.UpdateAbpClaimTypes = true;
    }

    internal static void ConfigureTokenLifetimes(OpenIddictServerBuilder builder)
    {
        builder.SetAuthorizationCodeLifetime(TimeSpan.FromMinutes(30));
        builder.SetAccessTokenLifetime(TimeSpan.FromMinutes(30));
        builder.SetIdentityTokenLifetime(TimeSpan.FromMinutes(30));
        builder.SetRefreshTokenLifetime(TimeSpan.FromDays(14));
    }

    internal static void ConfigureProductionCertificate(
        OpenIddictServerBuilder builder, string certPath, string certPassword)
    {
        // Read the certificate path/password from configuration or a secret store.
        builder.AddProductionEncryptionAndSigningCertificate(
            certPath,
            certPassword,
            X509KeyStorageFlags.MachineKeySet);

        builder.DisableAccessTokenEncryption();
    }

    internal static void DisableTransportSecurity(OpenIddictServerAspNetCoreOptions options)
    {
        options.DisableTransportSecurityRequirement = true;
    }

    internal static void RegisterClaimsPrincipalHandler(AbpOpenIddictClaimsPrincipalOptions options)
    {
        options.ClaimsPrincipalHandlers.Add<SampleClaimsPrincipalHandler>();
    }

    internal static bool IsRefreshTokenGrant(string grantType)
    {
        return grantType == OpenIddictConstants.GrantTypes.RefreshToken;
    }

    internal static void ConfigureTokenCleanup(TokenCleanupOptions options)
    {
        options.IsCleanupEnabled = true;
        options.CleanupPeriod = 3_600_000;
        options.MinimumTokenLifespan = TimeSpan.FromDays(14);
        options.MinimumAuthorizationLifespan = TimeSpan.FromDays(14);
    }
}

internal sealed class SampleClaimsPrincipalHandler : IAbpOpenIddictClaimsPrincipalHandler
{
    public Task HandleAsync(AbpOpenIddictClaimsPrincipalHandlerContext context)
    {
        _ = context.Principal;
        _ = context.OpenIddictRequest;
        return Task.CompletedTask;
    }
}
