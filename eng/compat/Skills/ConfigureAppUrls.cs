using System.Threading.Tasks;
using Volo.Abp.UI.Navigation.Urls;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureAppUrls
{
    internal static void Options(AppUrlOptions options)
    {
        ApplicationUrlDictionary apps = options.Applications;
        ApplicationUrlInfo info = apps["MVC"];
        info.RootUrl = "https://{{tenantName}}.example.com";
        info.Urls["PasswordReset"] = "account/reset-password";

        options.RedirectAllowedUrls.Add("https://*.apps.example.com");
    }

    internal static async Task Provider(IAppUrlProvider provider)
    {
        string url = await provider.GetUrlAsync("MVC", "PasswordReset");
        string? orNull = await provider.GetUrlOrNullAsync("MVC", "PasswordReset");
        string? normalized = await provider.NormalizeUrlAsync(url);
        bool allowed = await provider.IsRedirectAllowedUrlAsync(url);
    }
}
