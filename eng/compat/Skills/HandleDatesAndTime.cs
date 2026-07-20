// Compile-smoke for skill: abp-infrastructure/handle-dates-and-time
// Exercises the ABP clock/timing APIs the skill teaches.
using System;
using Volo.Abp.Timing;

namespace AbpSkillsCompat.Skills;

internal static class HandleDatesAndTime
{
    internal static void Api(IClock clock)
    {
        DateTime now = clock.Now;
        bool supportsMultipleTimezone = clock.SupportsMultipleTimezone;
        DateTime normalized = clock.Normalize(now);
        DateTimeKind kind = clock.Kind;
    }

    internal static void Options(AbpClockOptions options)
    {
        options.Kind = DateTimeKind.Utc;
    }

#if ABP_NEXT
    // ABP 10.6+ only (registered in eng/version-annotations.yaml). Compiled only in the
    // next-ABP build (-p:AbpNext=true), so the stable 10.5 gate stays green while the next
    // build actually type-checks this version-specific API.
    internal static DateTime ToUtc(ITimezoneProvider timezoneProvider, DateTime local)
    {
        return timezoneProvider.ConvertUnspecifiedToUtc(local, "UTC");
    }
#endif
}
