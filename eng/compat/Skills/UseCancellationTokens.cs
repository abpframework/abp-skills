// Compile-smoke for skill: abp-infrastructure/use-cancellation-tokens
// Exercises the ABP ICancellationTokenProvider ambient-cancellation APIs the skill teaches.
using System;
using System.Threading;
using System.Threading.Tasks;
using Volo.Abp.Threading;

namespace AbpSkillsCompat.Skills;

internal static class UseCancellationTokens
{
    internal static async Task UseAmbientProvider(ICancellationTokenProvider provider)
    {
        CancellationToken token = provider.Token;
        token.ThrowIfCancellationRequested();

        using (provider.Use(token))
        {
            await Task.CompletedTask;
        }
    }

    internal static void NullProvider()
    {
        ICancellationTokenProvider provider = NullCancellationTokenProvider.Instance;
        CancellationToken token = provider.Token;
    }
}
