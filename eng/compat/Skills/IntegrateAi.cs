// Compile-smoke for skill: abp-infrastructure/integrate-ai
// Exercises the ABP Volo.Abp.AI workspace/accessor APIs the skill teaches.
// Volo.Abp.AI ships in the 10.5 baseline this compat pins (build is 0-error).
using System.Threading.Tasks;
using Microsoft.Extensions.AI;
using Volo.Abp.AI;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

[DependsOn(typeof(AbpAIModule))]
internal class AiHostModule : AbpModule
{
}

[WorkspaceName("CommentSummarization")]
internal class CommentSummarizationWorkspace
{
}

internal static class IntegrateAi
{
    internal static void PreConfigureWorkspaces(AbpAIWorkspaceOptions options)
    {
        options.Workspaces.ConfigureDefault(workspace =>
        {
            workspace.ConfigureChatClient(chat =>
            {
                chat.Builder = null;
            });
        });

        options.Workspaces.Configure<CommentSummarizationWorkspace>(workspace =>
        {
            workspace.ConfigureKernel(kernel =>
            {
                kernel.Builder = null;
            });
        });

        string workspaceName = WorkspaceNameAttribute.GetWorkspaceName<CommentSummarizationWorkspace>();
    }

    internal static async Task<string?> Summarize(
        IChatClientAccessor<CommentSummarizationWorkspace> accessor,
        string comment)
    {
        Microsoft.Extensions.AI.IChatClient? client = accessor.ChatClient;
        return client is null
            ? null
            : (await client.GetResponseAsync(comment)).Text;
    }
}
