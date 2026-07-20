---
name: handle-validation-and-errors
description: >
  Validates DTOs/inputs and throws/localizes business errors in an ABP app.
  USE FOR: data annotations, IValidationEnabled, FluentValidation, BusinessException/UserFriendlyException, error codes, localizing error messages, mapping exceptions to HTTP status codes.
  DO NOT USE FOR: writing the application service itself or CrudAppService plumbing (use application-services); permission/authorization checks and AbpAuthorizationException policy (use permissions-and-authorization / authorize-resources).
license: MIT
---

# Validation & Error Handling in ABP

ABP builds on ASP.NET Core model validation and adds automatic validation, localization, and a standard exception-handling pipeline. Everything from the [ASP.NET Core validation docs](https://learn.microsoft.com/aspnet/core/mvc/models/validation) still applies.

## When to Use

- Validating DTOs/inputs with data annotations or `IValidatableObject`.
- Getting automatic method-argument validation via `IValidationEnabled`.
- Integrating FluentValidation into ABP's validation pipeline.
- Throwing business errors with `BusinessException` / `UserFriendlyException`.
- Localizing error messages by error code.
- Mapping exception types to HTTP status codes.

## When Not to Use

- **Writing the application service or CRUD plumbing itself** — use the application-services skill; this skill only covers the validation/error concerns inside it.
- **Authorization checks and `AbpAuthorizationException` policy** — use permissions-and-authorization / authorize-resources; here it appears only in the status-code mapping table.

## DTO Validation

Use standard data annotation attributes on DTOs. When a DTO is a parameter to an application service or controller action, ABP validates it automatically and throws an `AbpValidationException` on failure. (The attribute messages are localized only when the DTO's assembly is registered for data-annotations localization — see below — otherwise the raw attribute message is used.)

```csharp
public class CreateBookDto
{
    [Required]
    [StringLength(100)]
    public string Name { get; set; }

    [Range(0, 999.99)]
    public decimal Price { get; set; }
}
```

For custom cross-field logic, implement `IValidatableObject`:

```csharp
public class CreateBookDto : IValidatableObject
{
    [Required] public string Name { get; set; }
    [Required] public string Description { get; set; }

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
```

Keep DTOs simple — don't put domain logic in `Validate`. Data annotation error messages are localized only when the DTO's assembly is registered for it (via `AddDataAnnotationsLocalization` / `AbpMvcDataAnnotationsLocalizationOptions.AssemblyResources`); otherwise the raw attribute message is used.

### IValidationEnabled

`IValidationEnabled` is an empty marker interface. Any DI-registered class that implements it gets automatic method-argument validation. All application services implement it already. ABP uses dynamic proxying/interception, so the method must be **virtual** or the service must be called through an **interface**.

```csharp
public class MyService : ITransientDependency, IValidationEnabled
{
    public virtual async Task DoItAsync(MyInput input) { /* input is validated */ }
}
```

Disable with `[DisableValidation]` on a method, class, or property.

### AbpValidationException

ABP throws `AbpValidationException` when validation fails. Its `ValidationErrors` holds the error list, its log level is `Warning`, and ABP converts it to an HTTP 400 response automatically. You can throw it yourself but rarely need to.

## FluentValidation Integration

Add the `Volo.Abp.FluentValidation` package (`abp add-package Volo.Abp.FluentValidation`) and depend on `AbpFluentValidationModule`. Then write standard FluentValidation validators — ABP discovers them and runs them as part of the same validation pipeline.

```csharp
public class CreateUpdateBookDtoValidator : AbstractValidator<CreateUpdateBookDto>
{
    public CreateUpdateBookDtoValidator()
    {
        RuleFor(x => x.Name).Length(3, 10);
        RuleFor(x => x.Price).ExclusiveBetween(0.0f, 999.0f);
    }
}
```

## Business Exceptions

Most of your own errors are business exceptions. `BusinessException` implements `IBusinessException`, `IHasErrorCode`, `IHasErrorDetails`, and `IHasLogLevel` (default log level `Warning`). All its constructor arguments are optional; usually you set an error `Code` or a `Message`.

```csharp
throw new BusinessException(QaErrorCodes.CanNotVoteYourOwnAnswer);
```

The `Code` follows the format `<code-namespace>:<error-code>` (e.g. `Volo.Qa:010002`). The code-namespace is unique to your module/application and is the key used for localization.

Attach message parameters via the `Data` dictionary; there is a `WithData` shortcut that is chainable:

```csharp
throw new BusinessException("App:010046").WithData("UserName", "john");
```

## Localizing Error Messages

Two models:

**User-friendly exceptions.** `UserFriendlyException` implements `IUserFriendlyException` (which derives from `IBusinessException`). ABP sends its `Message` and `Details` to the client unchanged — no localization needed, or localize it yourself with the string localizer at throw time.

```csharp
throw new UserFriendlyException(_stringLocalizer["UserNameShouldBeUniqueMessage", "john"]);
```

**Error codes (recommended for advanced cases).** Instead of localizing at throw time, map a code-namespace to a localization resource once, then localize by the error code key. This avoids needing the localizer everywhere (e.g. in static contexts or entity methods).

```csharp
services.Configure<AbpExceptionLocalizationOptions>(options =>
{
    options.MapCodeNamespace("Volo.Qa", typeof(QaResource));
});
```

Add the error code as a key in the resource's `en.json`:

```json
{
  "culture": "en",
  "texts": {
    "Volo.Qa:010002": "You can not vote your own answer!",
    "App:010046": "Username should be unique. '{UserName}' is already taken!"
  }
}
```

If no localized string is defined for a code, ABP sends a default error message to the client — it does **not** fall back to the exception's `Message` property. Use `UserFriendlyException` when you want the raw message shown.

## HTTP Status Code Mapping

ABP picks a status code automatically for common exception types:

- `AbpAuthorizationException` → `401` if not logged in, `403` if logged in
- `AbpValidationException` → `400`
- `EntityNotFoundException` → `404`
- `AbpDbConcurrencyException` → `409`
- `IBusinessException` / `IUserFriendlyException` → `403`
- `NotImplementedException` → `501`
- anything else → `500` (treated as an infrastructure error)

Override per error code with `AbpExceptionHttpStatusCodeOptions`:

```csharp
services.Configure<AbpExceptionHttpStatusCodeOptions>(options =>
{
    options.Map("Volo.Qa:010002", HttpStatusCode.Conflict);
});
```

## Validation

- Pass an invalid DTO into an app service / auto API controller and confirm an `AbpValidationException` → HTTP 400 response, with `validationErrors` populated in the JSON.
- Throw a `BusinessException` with a mapped error code and confirm the localized text from `en.json` reaches the client (not the raw `Message`).
- Confirm the response body is a `RemoteServiceErrorResponse` with a single `error` object holding `code` / `message`.
- Verify a code mapped via `AbpExceptionHttpStatusCodeOptions.Map(...)` returns the overridden status code.

## Common Pitfalls

- Data annotation messages are **not** localized unless the DTO's assembly is registered for data-annotations localization (`AddDataAnnotationsLocalization` / `AbpMvcDataAnnotationsLocalizationOptions.AssemblyResources`); otherwise the raw attribute message shows.
- `IValidationEnabled` needs the method to be **virtual** or the service to be called through an **interface** — ABP relies on dynamic proxying/interception, so direct concrete calls to non-virtual methods bypass validation.
- An error code with no localized string falls back to ABP's default message, **not** to the exception's `Message`. Use `UserFriendlyException` when you want the raw message shown.
- The error JSON is a `RemoteServiceErrorResponse` with a single `error` object (a `RemoteServiceErrorInfo`) holding `code`, `message`, `details`, `data`, and `validationErrors` — i.e. `{ "error": { "code": ..., "message": ... } }` — filled based on which interfaces the exception implements.
- Control what reaches clients with `AbpExceptionHandlingOptions` (`SendExceptionsDetailsToClients`, `SendStackTraceToClients`).
- Set an exception's log level by implementing `IHasLogLevel`; add extra logging with `IExceptionWithSelfLogging`.
- To react when ABP handles an exception, derive from `ExceptionSubscriber` and override `HandleAsync`.
