// Compile-smoke for skill: abp-module-development/handle-validation-and-errors
// Exercises data annotations, IValidatableObject, IValidationEnabled, AbpValidationException,
// BusinessException/UserFriendlyException, EntityNotFoundException, and exception options.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Net;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.AspNetCore.ExceptionHandling;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Localization.ExceptionHandling;
using Volo.Abp.Validation;

namespace AbpSkillsCompat.Skills;

internal sealed class ValCreateBookDto : IValidatableObject
{
    [Required]
    [StringLength(100)]
    public string Name { get; set; } = string.Empty;

    [Range(0, 999.99)]
    public decimal Price { get; set; }

    [Required]
    public string Description { get; set; } = string.Empty;

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (Name == Description)
        {
            yield return new ValidationResult(
                "Name and Description can not be the same!",
                new[] { "Name", "Description" });
        }
    }
}

internal sealed class ValidatedService : ITransientDependency, IValidationEnabled
{
    public Task DoItAsync(ValCreateBookDto input)
    {
        return Task.CompletedTask;
    }
}

internal static class HandleValidationAndErrors
{
    internal static void ThrowBusinessErrors()
    {
        throw new BusinessException("App:010046").WithData("UserName", "john");
    }

    internal static void ThrowUserFriendly()
    {
        throw new UserFriendlyException("Username should be unique.");
    }

    internal static void ThrowFrameworkExceptions()
    {
        throw new AbpValidationException("invalid");
    }

    internal static void ThrowNotFound()
    {
        throw new EntityNotFoundException(typeof(ValCreateBookDto), Guid.NewGuid());
    }

    internal static void ConfigureExceptionOptions(IServiceCollection services)
    {
        services.Configure<AbpExceptionLocalizationOptions>(options =>
        {
            options.MapCodeNamespace("Volo.Qa", typeof(HandleValidationAndErrors));
        });

        services.Configure<AbpExceptionHttpStatusCodeOptions>(options =>
        {
            options.Map("Volo.Qa:010002", HttpStatusCode.Conflict);
        });
    }
}
