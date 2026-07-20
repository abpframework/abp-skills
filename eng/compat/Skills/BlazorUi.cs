// Compile-smoke for skill: abp-ui/blazor-ui
// Exercises AbpComponentBase (LocalizationResource, L, CurrentUser, Message, Notify,
// ObjectMapper.Map, AuthorizationService, Alerts, Clock, HandleErrorAsync) as the root Blazor
// base class, and AbpCrudPageBase (Volo.Abp.BlazoriseUI) as the CRUD-screen base.
// Razor markup and render/hosting models in the skill are not compile-checked here.
using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Volo.Abp.AspNetCore.Components;
using Volo.Abp.AspNetCore.Components.Alerts;
using Volo.Abp.Application.Dtos;
using Volo.Abp.Application.Services;
using Volo.Abp.BlazoriseUI;
using Volo.Abp.Timing;
using MyProjectResource = AbpSkillsCompat.Skills.BlazorBook;

namespace AbpSkillsCompat.Skills;

internal sealed class BlazorBook
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class BlazorBookDto : EntityDto<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal interface IBlazorBookAppService : ICrudAppService<BlazorBookDto, Guid>
{
}

internal sealed class BookList : AbpComponentBase
{
    public BookList()
    {
        LocalizationResource = typeof(MyProjectResource);
    }

    public async Task Exercise()
    {
        var title = L["BookName"];
        var userId = CurrentUser.Id;
        var tenantId = CurrentTenant.Id;

        // Reference the documented base members (not just declare AbpComponentBase).
        IAuthorizationService authorizationService = AuthorizationService;
        AlertList alerts = Alerts;
        IClock clock = Clock;
        _ = (authorizationService, alerts, clock.Now);

        try
        {
            await Message.Info(title);
            await Notify.Success(title);

            // Actually call ObjectMapper.Map<,> so a signature change breaks the build.
            BlazorBookDto dto = ObjectMapper.Map<BlazorBook, BlazorBookDto>(new BlazorBook());
            _ = dto.Name;
        }
        catch (Exception ex)
        {
            await HandleErrorAsync(ex);
        }
    }
}

// AbpCrudPageBase (Volo.Abp.BlazoriseUI) — the CRUD-screen base the skill lists alongside
// AbpComponentBase. Deriving the closed generic proves the type/constraints still exist.
internal sealed class BlazorBookCrudPage
    : AbpCrudPageBase<IBlazorBookAppService, BlazorBookDto, Guid>
{
}
