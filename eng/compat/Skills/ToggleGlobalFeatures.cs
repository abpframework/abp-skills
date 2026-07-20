// Compile-smoke for skill: abp-infrastructure/toggle-global-features
// Exercises the ABP Global Features startup-switch APIs the skill teaches.
using System.Collections.Generic;
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.GlobalFeatures;

namespace AbpSkillsCompat.Skills;

[GlobalFeatureName("Shopping.Payment")]
internal class PaymentFeature
{
}

[RequiresGlobalFeature(typeof(PaymentFeature))]
internal class PaymentController : AbpController
{
}

internal static class ToggleGlobalFeatures
{
    internal static void Configure()
    {
        GlobalFeatureManager.Instance.Enable<PaymentFeature>();
        GlobalFeatureManager.Instance.Disable("Shopping.Payment");

        bool enabled = GlobalFeatureManager.Instance.IsEnabled<PaymentFeature>();
        IEnumerable<string> names = GlobalFeatureManager.Instance.GetEnabledFeatureNames();

        string featureName = GlobalFeatureNameAttribute.GetName<PaymentFeature>();
    }
}
