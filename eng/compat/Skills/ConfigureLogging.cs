using System;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Volo.Abp;
using Volo.Abp.Logging;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

internal sealed class LoggingCategory
{
}

internal static class ConfigureLogging
{
    internal static void InitLogger(ServiceConfigurationContext context)
    {
        ILogger<LoggingCategory> logger = context.Services.GetInitLogger<LoggingCategory>();
        logger.LogDebug("Configuring module services");
    }

    internal static void ExceptionLogging(ILogger logger, Exception exception)
    {
        logger.LogException(exception, LogLevel.Error);
        logger.LogException(exception);
    }

    internal static void InitLoggerFactory(IInitLoggerFactory factory)
    {
        var l = factory.Create<LoggingCategory>();
    }
}
