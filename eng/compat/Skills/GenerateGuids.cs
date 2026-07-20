// Compile-smoke for skill: abp-infrastructure/generate-guids
// Exercises the ABP GUID-generation APIs the skill teaches.
using System;
using Microsoft.Extensions.Options;
using Volo.Abp.Guids;

namespace AbpSkillsCompat.Skills;

internal static class GenerateGuids
{
    internal static void Api(IGuidGenerator guidGenerator)
    {
        Guid id = guidGenerator.Create();
    }

    internal static void SequentialOptions(AbpSequentialGuidGeneratorOptions options)
    {
        SequentialGuidType type = options.DefaultSequentialGuidType ?? SequentialGuidType.SequentialAtEnd;
        _ = SequentialGuidType.SequentialAsString;
        _ = SequentialGuidType.SequentialAsBinary;
    }

    internal static void SequentialGenerator(IOptions<AbpSequentialGuidGeneratorOptions> options)
    {
        var generator = new SequentialGuidGenerator(options);
        Guid id = generator.Create();
    }
}
