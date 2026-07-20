---
name: manipulate-images
description: "Compress/resize image streams or byte arrays via ABP IImageCompressor and IImageResizer with a separate provider. USE FOR: ImageCompressResult and ImageResizeResult; ImageResizeArgs and ImageResizeMode; stream/byte-array overloads; ImageSharp, MagickNet, or SkiaSharp. DO NOT USE FOR: upload authorization (permissions-and-authorization); CSRF on uploads (secure-web-requests); caching images (distributed-caching-and-locking); background jobs (background-jobs-and-events)."
license: MIT
---

# Manipulate Images in ABP

Use the abstractions from `Volo.Abp.Imaging.Abstractions`, then normally select one suitable provider package. The abstraction coordinates registered contributors; it does not contain an image codec by itself.

## When to Use

- Compress an image only when a provider can produce a useful result.
- Resize image streams or byte arrays to requested dimensions.
- Keep application code independent of ImageSharp, Magick.NET, or SkiaSharp.
- Propagate cancellation into image decoding, encoding, and stream copying.

## When Not to Use

- **Authorize uploads** — use permissions-and-authorization; use secure-web-requests only for CSRF/antiforgery on the upload endpoint.
- **Cache processed image results or coordinate distributed work** — use distributed-caching-and-locking.
- **Run image processing as a background job** — use background-jobs-and-events for job orchestration.

## How it works

### Select a provider package

The common package is `Volo.Abp.Imaging.Abstractions` and its module is `AbpImagingAbstractionsModule`. Real implementations are separate packages and modules:

| Package | Module | Underlying library |
| --- | --- | --- |
| `Volo.Abp.Imaging.ImageSharp` | `AbpImagingImageSharpModule` | SixLabors.ImageSharp |
| `Volo.Abp.Imaging.MagickNet` | `AbpImagingMagickNetModule` | Magick.NET |
| `Volo.Abp.Imaging.SkiaSharp` | `AbpImagingSkiaSharpModule` | SkiaSharp |

Depend on the selected provider module; it already depends on the abstractions module:

```csharp
using Volo.Abp.Imaging;
using Volo.Abp.Modularity;

[DependsOn(typeof(AbpImagingImageSharpModule))]
public class MediaModule : AbpModule
{
}
```

Provider format support and resize behavior are provider-specific. Do not add multiple providers unless contributor ordering and fallback behavior have been deliberately tested.

### Compress an image

`IImageCompressor` has `Stream` and `byte[]` overloads. Both accept an optional MIME type and cancellation token:

```csharp
var result = await _imageCompressor.CompressAsync(
    imageBytes,
    "image/jpeg",
    cancellationToken);

if (result.State == ImageProcessState.Done)
{
    imageBytes = result.Result;
}
```

`ImageCompressResult<T>` inherits `Result` and `State` from `ImageProcessResult<T>`. Handle every state:

- `Done`: consume the returned result.
- `Canceled`: the contributor chose not to replace the original result. For the ImageSharp compressor, this means the encoded result was not smaller; it is not cancellation-token signaling.
- `Unsupported`: no contributor handled the input.

For `Canceled` and `Unsupported`, the result can be the original input.

### Resize an image

`IImageResizer` also has `Stream` and `byte[]` overloads:

```csharp
var args = new ImageResizeArgs(
    width: 640,
    height: 360,
    mode: ImageResizeMode.Crop);

var result = await _imageResizer.ResizeAsync(
    imageBytes,
    args,
    "image/jpeg",
    cancellationToken);

if (result.State != ImageProcessState.Done)
{
    throw new InvalidOperationException($"Image resize failed: {result.State}");
}

var resizedBytes = result.Result;
```

`ImageResizeArgs.Width` and `Height` are `uint`; omitted values become `0`. `Mode` defaults to `ImageResizeMode.Default`. Before invoking contributors, `ImageResizer` replaces `Default` with `ImageResizeOptions.DefaultResizeMode`, whose default is `None`.

Configure a common default only when every selected provider supports it:

```csharp
Configure<ImageResizeOptions>(options =>
{
    options.DefaultResizeMode = ImageResizeMode.Max;
});
```

### Handle streams carefully

Unreadable streams return `Unsupported`. A readable non-seekable stream is copied into a `MemoryStream`. The coordinator seeks streams back to position zero when possible, and a successful contributor can return a new stream. Always consume `result.Result`; do not assume the input stream contains processed data.

## Validation

- Resolve both interfaces and confirm the expected provider contributors are registered.
- Test every MIME type the application accepts with both valid and malformed data.
- Assert output dimensions, `State`, stream position, and whether the returned object is new or original.
- Test a non-seekable input stream and a pre-canceled token.
- Compare output size before treating compression as successful.

## Common Pitfalls

- **Installing only `Volo.Abp.Imaging.Abstractions`** — no codec contributor will process the image.
- **Ignoring `State`** — `Result` can contain the untouched input for `Canceled` or `Unsupported`.
- **Reading the original stream after processing** — successful processing can return a different stream.
- **Confusing `ImageProcessState.Canceled` with `OperationCanceledException`** — the ImageSharp compressor uses that state when compression would not reduce size.
- **Assuming all providers support identical MIME types and modes** — verify the chosen provider.
- **Leaving `ImageResizeMode.Default` unexplained** — it resolves through `ImageResizeOptions.DefaultResizeMode`, which is `None` by default.
