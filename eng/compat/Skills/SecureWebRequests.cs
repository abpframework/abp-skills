// Compile-smoke for skill: abp-runtime/secure-web-requests
// Exercises the ABP antiforgery + security-headers APIs the skill teaches.
using Microsoft.AspNetCore.Builder;
using Volo.Abp.AspNetCore.Mvc.AntiForgery;
using Volo.Abp.AspNetCore.Security;

namespace AbpSkillsCompat.Skills;

internal static class SecureWebRequests
{
    internal static void AntiForgeryOptions(AbpAntiForgeryOptions options)
    {
        options.AutoValidate = true;
        options.AutoValidateFilter = controllerType =>
            controllerType.Namespace?.StartsWith("MyCompany.MyProduct") == true;
        _ = options.TokenCookie;
        _ = options.AutoValidateIgnoredHttpMethods;
    }

    internal static void GenerateToken(IAbpAntiForgeryManager antiforgeryManager)
    {
        antiforgeryManager.SetCookie();
        string token = antiforgeryManager.GenerateToken();
    }

    internal static void SecurityHeaderOptions(AbpSecurityHeadersOptions options)
    {
        options.Headers["Referrer-Policy"] = "strict-origin-when-cross-origin";
        options.UseContentSecurityPolicyHeader = true;
        options.ContentSecurityPolicyValue =
            "default-src 'self'; object-src 'none'; form-action 'self'; frame-ancestors 'none'";
        options.IgnoredScriptNoncePaths.Add("/external-callback");
    }

    internal static void Middleware(IApplicationBuilder app)
    {
        app.UseRouting();
        app.UseAbpSecurityHeaders();
        app.UseConfiguredEndpoints();
    }

    [IgnoreAbpSecurityHeader]
    internal class ExcludedEndpoint
    {
    }

#if ABP_NEXT
    // ABP 10.6+ only (registered in eng/version-annotations.yaml). Compiled only in the
    // next-ABP build (-p:AbpNext=true), so the stable 10.5 gate stays green while the next
    // build actually type-checks these version-specific APIs.
    internal static void NextAntiForgery(AbpAntiForgeryOptions options)
    {
        options.NormalizeUserIdClaimIssuer = true;
        _ = typeof(AbpAntiforgery);
    }
#endif
}
