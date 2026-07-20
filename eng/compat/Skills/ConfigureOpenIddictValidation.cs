// Compile-smoke for skill: abp-authentication/configure-openiddict-validation
// Exercises the ABP validation pipeline middleware UseAbpOpenIddictValidation, the ABP
// JWT-bearer wrapper AddAbpJwtBearer (remote-authority pattern), and the Identity module's
// ForwardIdentityAuthenticationForBearer helper. The OpenIddictValidationBuilder /
// OpenIddict-native builder methods are configured through the OpenIddict packages the
// skill documents and are not smoked here.
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureOpeniddictValidation
{
    internal static void Pipeline(IApplicationBuilder app)
    {
        app.UseAbpOpenIddictValidation();
    }

    internal static void RemoteBearer(IServiceCollection services)
    {
        services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddAbpJwtBearer(options =>
            {
                options.Authority = "https://auth.example.com";
                options.Audience = "MyApi";
            });

        services.ForwardIdentityAuthenticationForBearer(JwtBearerDefaults.AuthenticationScheme);
    }
}
