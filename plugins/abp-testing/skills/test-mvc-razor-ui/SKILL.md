---
name: test-mvc-razor-ui
description: >
  Write ABP MVC/Razor integration tests that drive real HTTP against the app through AbpWebApplicationFactoryIntegratedTest.
  USE FOR: subclassing AbpWebApplicationFactoryIntegratedTest with the SUT Program type (not a module); the Client (AllowAutoRedirect is false, so unauthenticated requests return 302); GetRequiredService/GetService/GetUrl; the per-solution GetResponseAsStringAsync/GetResponseAsObjectAsync/GetResponseAsync helpers (Shouldly-based, copied into the WebTestBase — not shipped in any NuGet package); the web test module (DependsOn AbpAspNetCoreTestBaseModule plus the SUT web module, the CompiledRazorAssemblyPart registration, and the OpenIddict dev certificate); and faking a logged-in user with the FakeAuthentication scheme plus FakeUserClaims pushing an AbpClaimTypes.UserId claim.
  DO NOT USE FOR: application-service/repository integration tests (test-abp-applications); Angular component tests (test-angular-ui); production hosting/middleware configuration (configure-production-hosting).
license: MIT
---

# Test MVC / Razor UI (ABP)

ABP's `Volo.Abp.AspNetCore.TestBase` boots the real web app in-process so you can request pages/endpoints over HTTP and assert on the response. This is the ASP.NET Core web counterpart to the application-layer `*TestBase` chain.

## When to Use

- Requesting an MVC action or Razor page over HTTP and asserting on the HTML/JSON.
- Verifying routing, an authenticated page, or an anonymous 302-to-login.

## When Not to Use

- **Application services, domain services, repositories** — use **test-abp-applications** (no web host needed).
- **Angular component tests** — use **test-angular-ui**.
- **Configuring production hosting/middleware** — use **configure-production-hosting**.

## The test base

Subclass `AbpWebApplicationFactoryIntegratedTest<TProgram>` where `TProgram` is the **SUT's `Program` entry-point class**, not an ABP module. It gives you `Client` (an `HttpClient` with **`AllowAutoRedirect = false`**, so an unauthenticated request returns a `302`, not the login page body), plus `GetService<T>` / `GetRequiredService<T>` / `GetUrl<TController>()`.

The `GetResponseAs*` helpers the ABP docs show are **not in the package** — each solution copies them into its own `*WebTestBase` (they use Shouldly). Put them there:

```csharp
using System.Net;
using System.Text.Json;
using Shouldly;
using Volo.Abp.AspNetCore.TestBase;
using MyCompanyName.MyProjectName.Web;   // the SUT's Program lives here

public abstract class MyProjectNameWebTestBase
    : AbpWebApplicationFactoryIntegratedTest<Program>
{
    protected virtual async Task<string> GetResponseAsStringAsync(
        string url, HttpStatusCode expectedStatusCode = HttpStatusCode.OK)
    {
        var response = await Client.GetAsync(url);
        response.StatusCode.ShouldBe(expectedStatusCode);
        return await response.Content.ReadAsStringAsync();
    }

    protected virtual async Task<T?> GetResponseAsObjectAsync<T>(
        string url, HttpStatusCode expectedStatusCode = HttpStatusCode.OK)
    {
        var str = await GetResponseAsStringAsync(url, expectedStatusCode);
        return JsonSerializer.Deserialize<T>(str, new JsonSerializerOptions(JsonSerializerDefaults.Web));
    }
}
```

A test then just requests a URL:

```csharp
public class Index_Tests : MyProjectNameWebTestBase
{
    [Fact]
    public async Task Welcome_Page()
    {
        var html = await GetResponseAsStringAsync("/");
        html.ShouldContain("Welcome");
    }
}
```

## The web test module

The web-test startup module depends on `AbpAspNetCoreTestBaseModule` **and the SUT's `*WebModule`**, and does two load-bearing things in `PreConfigureServices`: register a `CompiledRazorAssemblyPart` for the Web assembly (without it the compiled Razor pages 404), and turn on the OpenIddict development certificate.

```csharp
[DependsOn(
    typeof(AbpAspNetCoreTestBaseModule),
    typeof(MyProjectNameWebModule),
    typeof(MyProjectNameApplicationTestModule),
    typeof(MyProjectNameEntityFrameworkCoreTestModule)
)]
public class MyProjectNameWebTestModule : AbpModule
{
    public override void PreConfigureServices(ServiceConfigurationContext context)
    {
        context.Services.PreConfigure<IMvcBuilder>(b =>
            b.PartManager.ApplicationParts.Add(
                new CompiledRazorAssemblyPart(typeof(MyProjectNameWebModule).Assembly)));

        context.Services.GetPreConfigureActions<OpenIddictServerBuilder>().Clear();
        PreConfigure<AbpOpenIddictAspNetCoreOptions>(o =>
            o.AddDevelopmentEncryptionAndSigningCertificate = true);
    }
}
```

## Faking a logged-in user

There is **no built-in always-allow** for web tests, and the `FakeAuthentication` scheme + `FakeUserClaims` bag live in ABP's own test project — **not in any NuGet package**. Copy that pattern: register `AddAuthentication(...).AddFakeAuthentication()` in the test module, then per test resolve `FakeUserClaims` and push a claim before the request:

```csharp
var fakeClaims = GetRequiredService<FakeUserClaims>();
fakeClaims.Claims.Add(new Claim(AbpClaimTypes.UserId, userId.ToString()));
var page = await GetResponseAsStringAsync("/Identity/Users");   // now authenticated
```

With no claim pushed the request is anonymous, so a protected page returns `302` (remember `AllowAutoRedirect = false`).

## Validation

- Hit `/` and assert `200` + expected markup.
- Hit a protected page with no fake claim and assert `302`; push an `AbpClaimTypes.UserId` claim and assert `200`.

## Common Pitfalls

- **Passing a module type as the generic argument.** It's `AbpWebApplicationFactoryIntegratedTest<Program>` — the SUT entry-point class, not the ABP module.
- **Expecting `GetResponseAs*` from the package.** They aren't shipped; copy them into your `*WebTestBase`.
- **Expecting a login page body on an unauthenticated request.** `Client` has `AllowAutoRedirect = false`, so you get a `302` — assert the status, not page content.
- **Razor pages 404 in tests.** You skipped the `CompiledRazorAssemblyPart` registration for the Web assembly.
- **Looking for a built-in fake login.** Copy the `FakeAuthentication` scheme + `FakeUserClaims` pattern; it isn't in a NuGet package.
