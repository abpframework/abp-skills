#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "Skills"
PROJECTS_DIR = ROOT / "Projects"
SOLUTION = ROOT / "AbpSkillsCompat.slnx"

PACKAGES = {
    "AddSignalrRealtime": ["Volo.Abp.AspNetCore.SignalR", "Volo.Abp.Core"],
    "ApplicationServices": ["Volo.Abp.Ddd.Application", "Volo.Abp.Ddd.Domain", "Volo.Abp.ObjectMapping", "Volo.Abp.Uow", "Volo.Abp.Validation"],
    "ApplyDataFilters": ["Volo.Abp.Core", "Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.EntityFrameworkCore", "Volo.Abp.MongoDB", "Volo.Abp.MultiTenancy.Abstractions"],
    "AuthorizeResources": ["Volo.Abp.Authorization", "Volo.Abp.Authorization.Abstractions", "Volo.Abp.MultiTenancy.Abstractions"],
    "BackgroundJobsAndEvents": ["Volo.Abp.BackgroundJobs.Abstractions", "Volo.Abp.BackgroundWorkers", "Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.EventBus.Abstractions", "Volo.Abp.Threading"],
    "BlazorUi": ["Volo.Abp.AspNetCore.Components", "Volo.Abp.BlazoriseUI", "Volo.Abp.Ddd.Application.Contracts", "Volo.Abp.Timing"],
    "BuildCrudApplicationServices": ["Volo.Abp.Ddd.Application", "Volo.Abp.Ddd.Application.Contracts", "Volo.Abp.Ddd.Domain"],
    "BuildMvcWidgets": ["Volo.Abp.AspNetCore.Mvc", "Volo.Abp.AspNetCore.Mvc.UI.Widgets"],
    "CacheEntities": ["Volo.Abp.Ddd.Domain"],
    "CheckSimpleState": ["Volo.Abp.Authorization", "Volo.Abp.Authorization.Abstractions", "Volo.Abp.Core"],
    "ConfigureAppUrls": ["Volo.Abp.UI.Navigation"],
    "ConfigureAuditLogging": ["Volo.Abp.AspNetCore", "Volo.Abp.Auditing", "Volo.Abp.Auditing.Contracts", "Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.ObjectExtending"],
    "ConfigureConnectionStrings": ["Volo.Abp.Data"],
    "ConfigureCors": ["Volo.Abp.AspNetCore"],
    "ConfigureDynamicClaims": ["Volo.Abp.AspNetCore.Authentication.JwtBearer", "Volo.Abp.Security"],
    "ConfigureLogging": ["Volo.Abp.Core"],
    "ConfigureMultiTenancy": ["Volo.Abp.AspNetCore.MultiTenancy", "Volo.Abp.BackgroundJobs.Abstractions", "Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.MultiTenancy.Abstractions"],
    "ConfigureOpenIddictAuthentication": ["Volo.Abp.OpenIddict.AspNetCore"],
    "ConfigureOpenIddictValidation": ["Volo.Abp.AspNetCore.Authentication.JwtBearer", "Volo.Abp.Identity.AspNetCore", "Volo.Abp.OpenIddict.AspNetCore"],
    "ConfigureProductionHosting": ["Volo.Abp.AspNetCore", "Volo.Abp.BackgroundJobs.Abstractions", "Volo.Abp.BackgroundWorkers", "Volo.Abp.Caching", "Volo.Abp.DistributedLocking.Abstractions", "Volo.Abp.Security"],
    "ConfigureSwaggerOpenapi": ["Volo.Abp.Swashbuckle"],
    "ConsumeRemoteServices": ["Volo.Abp.Http.Client", "Volo.Abp.Http.Client.IdentityModel", "Volo.Abp.Http.Client.IdentityModel.Web"],
    "CreatePluginModules": ["Volo.Abp.Core"],
    "CustomizeApplicationModules": ["Volo.Abp.Core", "Volo.Abp.Data", "Volo.Abp.ObjectExtending"],
    "DefineApplicationModules": ["Volo.Abp.Core"],
    "DesignModuleAndServiceCommunication": ["Volo.Abp.AspNetCore.Mvc", "Volo.Abp.Core", "Volo.Abp.Ddd.Application", "Volo.Abp.EventBus", "Volo.Abp.EventBus.Abstractions"],
    "DistributedCachingAndLocking": ["Volo.Abp.Caching", "Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.DistributedLocking.Abstractions", "Volo.Abp.Features", "Volo.Abp.Settings"],
    "EfCoreIntegration": ["Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.EntityFrameworkCore", "Volo.Abp.EntityFrameworkCore.SqlServer"],
    "EncryptStrings": ["Volo.Abp.Security"],
    "ExposeHttpApis": ["Volo.Abp.AspNetCore.Mvc", "Volo.Abp.Core"],
    "ExtendApplicationShell": ["Volo.Abp.AspNetCore.Mvc.UI", "Volo.Abp.AspNetCore.Mvc.UI.Theme.Shared", "Volo.Abp.Authorization", "Volo.Abp.UI"],
    "ExtendObjectsWithExtraProperties": ["Riok.Mapperly", "Volo.Abp.AutoMapper", "Volo.Abp.Ddd.Application.Contracts", "Volo.Abp.Ddd.Domain", "Volo.Abp.EntityFrameworkCore", "Volo.Abp.Mapperly", "Volo.Abp.MongoDB", "Volo.Abp.ObjectExtending"],
    "GenerateGuids": ["Volo.Abp.Guids"],
    "HandleDatesAndTime": ["Volo.Abp.Timing"],
    "HandleOptimisticConcurrency": ["Volo.Abp.Data", "Volo.Abp.Ddd.Application.Contracts", "Volo.Abp.Ddd.Domain"],
    "HandleValidationAndErrors": ["Volo.Abp.AspNetCore", "Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.Localization", "Volo.Abp.Validation", "Volo.Abp.Validation.Abstractions"],
    "IntegrateAi": ["Volo.Abp.AI", "Volo.Abp.AI.Abstractions", "Volo.Abp.Core"],
    "IntegrateAutofac": ["Volo.Abp.Autofac", "Volo.Abp.Core"],
    "IntegrateDaprServices": ["Volo.Abp.AspNetCore.Mvc.Dapr", "Volo.Abp.Core", "Volo.Abp.Dapr", "Volo.Abp.DistributedLocking.Abstractions", "Volo.Abp.DistributedLocking.Dapr", "Volo.Abp.EventBus.Dapr"],
    "LayeredArchitecture": ["Volo.Abp.Ddd.Application.Contracts", "Volo.Abp.Ddd.Domain"],
    "LocalizeApplications": ["Volo.Abp.Localization"],
    "ManageSettingsAndFeatures": ["Volo.Abp.FeatureManagement.Domain", "Volo.Abp.Features", "Volo.Abp.SettingManagement.Domain", "Volo.Abp.Settings", "Volo.Abp.Validation.Abstractions"],
    "ManageUnitsOfWork": ["Volo.Abp.AspNetCore", "Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.Uow"],
    "ManageVirtualFiles": ["Volo.Abp.Core", "Volo.Abp.VirtualFileSystem"],
    "ManipulateImages": ["Volo.Abp.Core", "Volo.Abp.Imaging.Abstractions", "Volo.Abp.Imaging.ImageSharp"],
    "MapObjectsAndDtos": ["Riok.Mapperly", "Volo.Abp.AutoMapper", "Volo.Abp.Core", "Volo.Abp.Mapperly", "Volo.Abp.ObjectExtending", "Volo.Abp.ObjectMapping"],
    "MenusAndLocalization": ["Volo.Abp.Localization", "Volo.Abp.Localization.Abstractions", "Volo.Abp.UI.Navigation"],
    "ModelDomainAggregates": ["Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.Guids", "Volo.Abp.Specifications"],
    "MongodbIntegration": ["Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.MongoDB"],
    "MvcRazorUi": ["Volo.Abp.AspNetCore.Mvc.UI", "Volo.Abp.AspNetCore.Mvc.UI.Bootstrap", "Volo.Abp.AspNetCore.Mvc.UI.Bundling.Abstractions"],
    "PermissionsAndAuthorization": ["Volo.Abp.Authorization", "Volo.Abp.Authorization.Abstractions", "Volo.Abp.Core", "Volo.Abp.MultiTenancy.Abstractions", "Volo.Abp.Security"],
    "PropagateCorrelationId": ["Volo.Abp.AspNetCore", "Volo.Abp.Core"],
    "QueryWithDapper": ["Volo.Abp.Core", "Volo.Abp.Dapper", "Volo.Abp.EntityFrameworkCore"],
    "ReadConfiguration": ["Volo.Abp.Core"],
    "RegisterAndReplaceServices": ["Volo.Abp.Core"],
    "RenderTextTemplates": ["Volo.Abp.TextTemplating.Core", "Volo.Abp.TextTemplating.Razor", "Volo.Abp.TextTemplating.Scriban"],
    "SendEmails": ["Volo.Abp.Emailing", "Volo.Abp.MailKit", "Volo.Abp.TextTemplating.Core"],
    "SecureWebRequests": ["Volo.Abp.AspNetCore", "Volo.Abp.AspNetCore.Mvc"],
    "SeedApplicationData": ["Volo.Abp.Core", "Volo.Abp.Data", "Volo.Abp.Ddd.Domain", "Volo.Abp.Guids", "Volo.Abp.MultiTenancy.Abstractions", "Volo.Abp.Uow"],
    "SendSms": ["Volo.Abp.Core", "Volo.Abp.Sms"],
    "SerializeJson": ["Volo.Abp.Json.Abstractions", "Volo.Abp.Json.SystemTextJson"],
    "StoreBlobs": ["Volo.Abp.BlobStoring", "Volo.Abp.BlobStoring.Aws", "Volo.Abp.BlobStoring.Azure", "Volo.Abp.BlobStoring.Database.Domain", "Volo.Abp.BlobStoring.Minio", "Volo.Abp.Core"],
    "TestAbpApplications": ["Volo.Abp.Authorization", "Volo.Abp.Authorization.Abstractions", "Volo.Abp.Core", "Volo.Abp.Data", "Volo.Abp.MultiTenancy.Abstractions", "Volo.Abp.Security", "Volo.Abp.TestBase", "Volo.Abp.Uow"],
    "TestMvcRazorUi": ["Volo.Abp.AspNetCore.TestBase"],
    "ToggleGlobalFeatures": ["Volo.Abp.AspNetCore.Mvc", "Volo.Abp.GlobalFeatures"],
    "UseAbpRepositories": ["Volo.Abp.Core", "Volo.Abp.Ddd.Domain", "Volo.Abp.Threading"],
    "UseAbpStandardEndpoints": ["Volo.Abp.AspNetCore.Mvc.Contracts", "Volo.Abp.ObjectExtending"],
    "UseCancellationTokens": ["Volo.Abp.Threading"],
    "UseHybridCaching": ["Volo.Abp.Caching"],
    "UseInterceptorsAndDynamicProxy": ["Volo.Abp.Core"],
    "VersionHttpApis": ["Volo.Abp.AspNetCore.Mvc", "Volo.Abp.Http.Client"],
}


def project_xml(skill: str, packages: list[str]) -> str:
    references = "\n".join(
        f'    <PackageReference Include="{package}" />' for package in sorted(packages)
    )
    return f'''<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="../../Skills/{skill}.cs" />
  </ItemGroup>
  <ItemGroup>
{references}
  </ItemGroup>
</Project>
'''


def main() -> None:
    skills = {path.stem for path in SKILLS_DIR.glob("*.cs")}
    configured = set(PACKAGES)
    if skills != configured:
        missing = sorted(skills - configured)
        extra = sorted(configured - skills)
        raise RuntimeError(f"Package map mismatch. Missing={missing}; extra={extra}")

    if PROJECTS_DIR.exists():
        shutil.rmtree(PROJECTS_DIR)
    PROJECTS_DIR.mkdir()

    project_files = []
    for skill in sorted(skills):
        project_dir = PROJECTS_DIR / skill
        project_dir.mkdir()
        project_file = project_dir / f"{skill}.csproj"
        project_file.write_text(project_xml(skill, PACKAGES[skill]), encoding="utf-8")
        project_files.append(project_file)

    subprocess.run(
        ["dotnet", "new", "sln", "--name", SOLUTION.stem, "--format", "slnx", "--force"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["dotnet", "sln", str(SOLUTION), "add", *map(str, project_files)],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
