// Compile-smoke for skill: abp-api/configure-swagger-openapi
// Exercises AddAbpSwaggerGen / AddAbpSwaggerGenWithOAuth, the SwaggerGenOptions
// extensions HideAbpEndpoints / CustomAbpSchemaIds, UseAbpSwaggerUI, and AbpSwaggerOidcFlows.
using System.Collections.Generic;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Swashbuckle;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureSwaggerOpenapi
{
    internal static void Register(IServiceCollection services)
    {
        services.AddAbpSwaggerGen(options =>
        {
            options.HideAbpEndpoints();
            options.CustomAbpSchemaIds();
        });

        services.AddAbpSwaggerGenWithOAuth(
            "https://localhost:44300",
            new Dictionary<string, string> { { "MyApi", "My API" } });
    }

    internal static void Ui(IApplicationBuilder app)
    {
        app.UseAbpSwaggerUI();
    }

    internal static string Flow()
    {
        return AbpSwaggerOidcFlows.AuthorizationCode;
    }
}
