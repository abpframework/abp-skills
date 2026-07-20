using System.Threading.Tasks;
using Volo.Abp.SimpleStateChecking;
using Volo.Abp.Authorization.Permissions;

namespace AbpSkillsCompat.Skills;

internal static class CheckSimpleState
{
    internal static async Task Manager(
        ISimpleStateCheckerManager<PermissionDefinition> manager,
        PermissionDefinition state,
        PermissionDefinition[] states)
    {
        bool one = await manager.IsEnabledAsync(state);
        SimpleStateCheckerResult<PermissionDefinition> many = await manager.IsEnabledAsync(states);
    }

    internal static void Contract(IHasSimpleStateCheckers<PermissionDefinition> hasCheckers)
    {
        System.Collections.Generic.List<ISimpleStateChecker<PermissionDefinition>> checkers = hasCheckers.StateCheckers;
    }

    internal static void Options(AbpSimpleStateCheckerOptions<PermissionDefinition> options)
    {
        var global = options.GlobalStateCheckers;
    }

    internal static void BuiltInConditions(PermissionDefinition definition)
    {
        definition.RequireAuthenticated();
        definition.RequirePermissions("MyPermission");
        definition.RequirePermissions(requiresAll: true, "A", "B");
    }
}

internal sealed class MyStateChecker : ISimpleStateChecker<PermissionDefinition>
{
    public Task<bool> IsEnabledAsync(SimpleStateCheckerContext<PermissionDefinition> context)
    {
        var sp = context.ServiceProvider;
        var st = context.State;
        return Task.FromResult(true);
    }
}
