// Compile-smoke for skill: abp-infrastructure/manipulate-images
// Exercises the ABP IImageCompressor / IImageResizer abstractions the skill teaches.
using System;
using System.Threading;
using System.Threading.Tasks;
using Volo.Abp.Imaging;
using Volo.Abp.Modularity;

namespace AbpSkillsCompat.Skills;

[DependsOn(typeof(AbpImagingImageSharpModule))]
internal class MediaModule : AbpModule
{
}

internal static class ManipulateImages
{
    internal static async Task Compress(
        IImageCompressor imageCompressor,
        byte[] imageBytes,
        CancellationToken cancellationToken)
    {
        ImageCompressResult<byte[]> result = await imageCompressor.CompressAsync(
            imageBytes,
            "image/jpeg",
            cancellationToken);

        if (result.State == ImageProcessState.Done)
        {
            imageBytes = result.Result;
        }
    }

    internal static async Task Resize(
        IImageResizer imageResizer,
        byte[] imageBytes,
        CancellationToken cancellationToken)
    {
        var args = new ImageResizeArgs(width: 640, height: 360, mode: ImageResizeMode.Crop);

        ImageResizeResult<byte[]> result = await imageResizer.ResizeAsync(
            imageBytes,
            args,
            "image/jpeg",
            cancellationToken);

        if (result.State != ImageProcessState.Done)
        {
            throw new InvalidOperationException($"Image resize failed: {result.State}");
        }

        byte[] resizedBytes = result.Result;
        uint width = args.Width;
        uint height = args.Height;
        _ = ImageProcessState.Canceled;
        _ = ImageProcessState.Unsupported;
    }

    internal static void Options(ImageResizeOptions options)
    {
        options.DefaultResizeMode = ImageResizeMode.Max;
    }
}
