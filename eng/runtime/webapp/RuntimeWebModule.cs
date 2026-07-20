using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Cors;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Volo.Abp;
using Volo.Abp.Application;
using Volo.Abp.Application.Services;
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.AspNetCore.TestBase;
using Volo.Abp.Autofac;
using Volo.Abp.Modularity;

namespace RuntimeWebApp;

[DependsOn(
    typeof(AbpAspNetCoreMvcModule),
    typeof(AbpAspNetCoreTestBaseModule),
    typeof(AbpDddApplicationModule),
    typeof(AbpAutofacModule)
)]
public class RuntimeWebModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        // Auto-expose IApplicationService implementations in this assembly as HTTP controllers.
        Configure<AbpAspNetCoreMvcOptions>(options =>
        {
            options.ConventionalControllers.Create(typeof(RuntimeWebModule).Assembly);
        });

        context.Services
            .AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
            .AddCookie(options => options.LoginPath = "/login");

        context.Services.Configure<ForwardedHeadersOptions>(options =>
        {
            options.ForwardedHeaders = ForwardedHeaders.XForwardedProto | ForwardedHeaders.XForwardedHost;
            // Test-only: the in-memory TestServer is not a loopback proxy, so trust it explicitly.
            // Production sets KnownProxies/KnownIPNetworks to the real proxy (see the skill).
            options.KnownIPNetworks.Clear();
            options.KnownProxies.Clear();
        });

        context.Services.AddCors(options =>
        {
            options.AddDefaultPolicy(builder =>
            {
                builder
                    .WithOrigins("https://example.com")
                    .WithAbpExposedHeaders()   // exposes _AbpErrorFormat + Abp-Tenant-Resolve-Error
                    .AllowAnyHeader()
                    .AllowAnyMethod();
            });
        });

        context.Services
            .AddHealthChecks()
            // a readiness-tagged check that fails, so /health/ready returns 503
            .AddCheck("ready-probe", () => HealthCheckResult.Unhealthy("down"), tags: new[] { "ready" });

        context.Services.Configure<AbpEndpointRouterOptions>(options =>
        {
            options.EndpointConfigureActions.Add(ctx =>
            {
                ctx.Endpoints.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false });
                ctx.Endpoints.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") });
            });
        });
    }

    public override void OnApplicationInitialization(ApplicationInitializationContext context)
    {
        var app = context.GetApplicationBuilder();
        app.UseForwardedHeaders();   // must run before routing/auth so the real scheme/host are seen
        app.UseRouting();
        app.UseCors();
        app.UseAuthentication();
        app.UseAuthorization();
        app.UseConfiguredEndpoints();
    }
}

[Route("api/ping")]
public class PingController : AbpController
{
    [HttpGet]
    public string Get() => "pong";
}

[Route("api/secure")]
public class SecureController : AbpController
{
    [Authorize]
    [HttpGet]
    public string Get() => "secret";
}

[Route("api/scheme")]
public class SchemeController : AbpController
{
    // Echoes what the app sees after forwarded headers are applied.
    [HttpGet]
    public string Get() => $"{Request.Scheme}|{Request.Host}";
}

public interface IGreetingAppService : IApplicationService
{
    Task<string> GetAsync();
}

// No controller attribute: ABP's conventional-controller convention auto-exposes this
// application service at /api/app/greeting.
public class GreetingAppService : ApplicationService, IGreetingAppService
{
    public Task<string> GetAsync() => Task.FromResult("hi");
}
