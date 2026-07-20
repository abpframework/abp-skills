// Compile-smoke for skill: abp-api/configure-cors
// Exercises the ABP-specific CORS helper WithAbpExposedHeaders on a CorsPolicyBuilder. The
// rest of the CORS pipeline the skill shows (AddCors / WithOrigins / SetIsOriginAllowedTo
// AllowWildcardSubdomains / UseCors) is plain ASP.NET Core and is not ABP surface.
using Microsoft.AspNetCore.Cors;
using Microsoft.AspNetCore.Cors.Infrastructure;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureCors
{
    internal static void BuildPolicy(CorsPolicyBuilder builder)
    {
        builder
            .WithOrigins("https://localhost:44307")
            .WithAbpExposedHeaders()
            .SetIsOriginAllowedToAllowWildcardSubdomains()
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    }
}
