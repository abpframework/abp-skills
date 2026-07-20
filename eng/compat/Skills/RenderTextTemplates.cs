// Compile-smoke for skill: abp-runtime/render-text-templates
// Exercises the ABP text-templating APIs the skill teaches: a TemplateDefinitionProvider
// selecting the Scriban and Razor engines + virtual-file content, and ITemplateRenderer.RenderAsync.
using System.Threading.Tasks;
using Volo.Abp.TextTemplating;
using Volo.Abp.TextTemplating.Razor;
using Volo.Abp.TextTemplating.Scriban;

namespace AbpSkillsCompat.Skills;

internal class DemoTemplateDefinitionProvider : TemplateDefinitionProvider
{
    public override void Define(ITemplateDefinitionContext context)
    {
        context.Add(
            new TemplateDefinition("Hello")
                .WithScribanEngine()
                .WithVirtualFilePath("/Demos/Hello/Hello.tpl", isInlineLocalized: true));

        context.Add(
            new TemplateDefinition("HelloRazor")
                .WithRazorEngine()
                .WithVirtualFilePath("/Demos/HelloRazor/HelloRazor.cshtml", isInlineLocalized: true));
    }
}

internal static class RenderTextTemplates
{
    internal static async Task<string> Render(ITemplateRenderer templateRenderer)
    {
        return await templateRenderer.RenderAsync("Hello", new { Name = "John" });
    }
}
