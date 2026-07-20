// Compile-smoke for skill: abp-infrastructure/serialize-json
// Exercises the ABP IJsonSerializer abstraction + option types the skill teaches.
using System;
using System.Text.Json.Serialization;
using Volo.Abp.Json;
using Volo.Abp.Json.SystemTextJson;

namespace AbpSkillsCompat.Skills;

internal static class SerializeJson
{
    internal static void Serialize(IJsonSerializer jsonSerializer, object payload, string json)
    {
        string text = jsonSerializer.Serialize(payload, camelCase: true, indented: false);
        var typed = jsonSerializer.Deserialize<object>(json, camelCase: true);
        object runtime = jsonSerializer.Deserialize(typeof(object), json, camelCase: false);
    }

    internal static void SystemTextJsonOptions(AbpSystemTextJsonSerializerOptions options)
    {
        options.JsonSerializerOptions.DefaultIgnoreCondition =
            JsonIgnoreCondition.WhenWritingNull;
    }

    internal static void DateTimeFormats(AbpJsonOptions options)
    {
        options.InputDateTimeFormats.Add("yyyy-MM-dd HH:mm:ss");
        options.OutputDateTimeFormat = "yyyy-MM-dd'T'HH:mm:ss'Z'";
    }
}
