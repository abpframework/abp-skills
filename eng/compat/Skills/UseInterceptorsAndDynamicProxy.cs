// Compile-smoke for skill: abp-infrastructure/use-interceptors-and-dynamic-proxy
// Exercises the ABP IAbpInterceptor / OnRegistered dynamic-proxy APIs the skill teaches.
using System;
using System.Reflection;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.DependencyInjection;
using Volo.Abp.DynamicProxy;

namespace AbpSkillsCompat.Skills;

internal class ExecutionTimeInterceptor : AbpInterceptor, ITransientDependency
{
    public override async Task InterceptAsync(IAbpMethodInvocation invocation)
    {
        MethodInfo method = invocation.Method;
        object?[] args = invocation.Arguments;
        object? target = invocation.TargetObject;

        try
        {
            await invocation.ProceedAsync();
        }
        finally
        {
            object returnValue = invocation.ReturnValue;
        }
    }
}

internal interface IExecutionTimeEnabled
{
}

internal static class UseInterceptorsAndDynamicProxy
{
    internal static void RegisterIfNeeded(IOnServiceRegistredContext context)
    {
        if (typeof(IExecutionTimeEnabled).IsAssignableFrom(context.ImplementationType))
        {
            context.Interceptors.TryAdd<ExecutionTimeInterceptor>();
        }
    }

    internal static void Wire(IServiceCollection services)
    {
        services.OnRegistered(RegisterIfNeeded);
    }
}
