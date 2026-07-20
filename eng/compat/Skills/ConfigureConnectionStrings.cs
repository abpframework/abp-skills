// Compile-smoke for skill: abp-data-access/configure-connection-strings
// Exercises [ConnectionStringName], AbpDbConnectionOptions grouping, and IConnectionStringResolver.
using System.Threading.Tasks;
using Volo.Abp.Data;

namespace AbpSkillsCompat.Skills;

[ConnectionStringName("AbpIdentity")]
internal class SecondaryDbContextMarker
{
}

internal static class ConfigureConnectionStrings
{
    internal static void GroupModules()
    {
        var options = new AbpDbConnectionOptions();
        options.Databases.Configure("MySecondaryDb", db =>
        {
            db.MappedConnections.Add("AbpIdentity");
            db.MappedConnections.Add("AbpPermissionManagement");
        });

        options.ConnectionStrings.Default = "Server=localhost;Database=MyMainDb;Trusted_Connection=True;";
        options.ConnectionStrings["AbpPermissionManagement"] = "Server=localhost;Database=MyPermissionDb;Trusted_Connection=True;";
    }

    internal static async Task<string> ResolveAsync(IConnectionStringResolver resolver)
    {
        return await resolver.ResolveAsync("AbpIdentity");
    }

    // Custom resolver deriving from the built-in default.
    internal sealed class CustomConnectionStringResolver : DefaultConnectionStringResolver
    {
        public CustomConnectionStringResolver(
            Microsoft.Extensions.Options.IOptionsMonitor<AbpDbConnectionOptions> options)
            : base(options)
        {
        }
    }
}
