// Compile-smoke for skill: abp-infrastructure/manage-settings-and-features
// Exercises the ABP settings + features definition/read/gate APIs the skill teaches.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Volo.Abp.Features;
using Volo.Abp.FeatureManagement;
using Volo.Abp.Settings;
using Volo.Abp.SettingManagement;
using Volo.Abp.Validation.StringValues;

namespace AbpSkillsCompat.Skills;

internal class SampleSettingDefinitionProvider : SettingDefinitionProvider
{
    public override void Define(ISettingDefinitionContext context)
    {
        context.Add(
            new SettingDefinition("MyApp.Smtp.Host", "127.0.0.1"),
            new SettingDefinition("MyApp.Smtp.Password", isEncrypted: true));
    }
}

internal class SampleFeatureDefinitionProvider : FeatureDefinitionProvider
{
    public override void Define(IFeatureDefinitionContext context)
    {
        FeatureGroupDefinition group = context.AddGroup("SampleApp");
        FeatureDefinition reporting = group.AddFeature("SampleApp.Reporting", defaultValue: "false");
        reporting.CreateChild("SampleApp.Reporting.Pdf", defaultValue: "false");
    }
}

internal class SampleSettingValueProvider : SettingValueProvider
{
    public SampleSettingValueProvider(ISettingStore settingStore)
        : base(settingStore)
    {
    }

    public override string Name => "Sample";

    public override Task<string?> GetOrNullAsync(SettingDefinition setting)
        => Task.FromResult<string?>(null);

    public override Task<List<SettingValue>> GetAllAsync(SettingDefinition[] settings)
        => Task.FromResult(new List<SettingValue>());
}

internal class SampleFeatureValueProvider : FeatureValueProvider
{
    public SampleFeatureValueProvider(IFeatureStore featureStore)
        : base(featureStore)
    {
    }

    public override string Name => "Sample";

    public override Task<string?> GetOrNullAsync(FeatureDefinition feature)
        => Task.FromResult<string?>(null);
}

internal static class ManageSettingsAndFeatures
{
    internal static void RegisterValueProviders(AbpSettingOptions settingOptions, AbpFeatureOptions featureOptions)
    {
        settingOptions.ValueProviders.Add<SampleSettingValueProvider>();
        featureOptions.ValueProviders.Add<SampleFeatureValueProvider>();
    }

    internal static void DefineSettings(ISettingDefinitionContext context)
    {
        context.Add(
            new SettingDefinition("Smtp.Host", "127.0.0.1"),
            new SettingDefinition("Smtp.Password", isEncrypted: true));

        SettingDefinition? existing = context.GetOrNull("Abp.Mailing.Smtp.Host");
        if (existing != null)
        {
            existing.DefaultValue = "mail.mydomain.com";
        }
    }

    internal static async Task ReadSettings(ISettingProvider settingProvider)
    {
        string? userName = await settingProvider.GetOrNullAsync("Smtp.UserName");
        bool enableSsl = await settingProvider.IsTrueAsync("Smtp.EnableSsl");
        int port = await settingProvider.GetAsync<int>("Smtp.Port");
    }

    internal static void DefineFeatures(IFeatureDefinitionContext context)
    {
        FeatureGroupDefinition group = context.AddGroup("MyApp");
        group.AddFeature("MyApp.PdfReporting", defaultValue: "false");
        group.AddFeature(
            "MyApp.MaxProductCount",
            defaultValue: "10",
            valueType: new FreeTextStringValueType(new NumericValueValidator(0, 1000000)));
    }

    internal static async Task CheckFeatures(IFeatureChecker featureChecker)
    {
        bool enabled = await featureChecker.IsEnabledAsync("MyApp.PdfReporting");
        int max = await featureChecker.GetAsync<int>("MyApp.MaxProductCount");
        await featureChecker.CheckEnabledAsync("MyApp.PdfReporting");
    }

    internal static async Task ManageFeatures(IFeatureManager featureManager, Guid tenantId)
    {
        await featureManager.SetForTenantAsync(tenantId, "MyApp.PdfReporting", true.ToString());
    }

    internal static async Task ManageSettings(ISettingManager settingManager, Guid tenantId, Guid userId)
    {
        await settingManager.SetGlobalAsync("MyApp.SmtpHost", "smtp.acme.com");
        await settingManager.SetForTenantAsync(tenantId, "MyApp.SmtpHost", "smtp.tenant.com");
        await settingManager.SetForUserAsync(userId, "MyApp.Theme", "dark");
    }

    internal class GatedService
    {
        [RequiresFeature("MyApp.PdfReporting")]
        internal virtual Task GetPdfReportAsync() => Task.CompletedTask;

        [RequiresFeature("MyApp.PdfReporting", "MyApp.MaxProductCount", RequiresAll = true)]
        internal virtual Task GetAllGatedAsync() => Task.CompletedTask;
    }
}
