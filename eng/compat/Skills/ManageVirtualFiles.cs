// Compile-smoke for skill: abp-files/manage-virtual-files
// Exercises AbpVirtualFileSystemOptions.FileSets (AddEmbedded / ReplaceEmbeddedByPhysical)
// and reading through IVirtualFileProvider + ReadAsString.
using System.IO;
using Microsoft.Extensions.FileProviders;
using Volo.Abp.DependencyInjection;
using Volo.Abp.VirtualFileSystem;

namespace AbpSkillsCompat.Skills;

internal sealed class SampleVfsModule
{
}

internal static class ManageVirtualFiles
{
    internal static void RegisterEmbedded(AbpVirtualFileSystemOptions options)
    {
        options.FileSets.AddEmbedded<SampleVfsModule>();
        options.FileSets.AddEmbedded<SampleVfsModule>(
            baseNamespace: "Acme.BookStore",
            baseFolder: "/MyResources");
    }

    internal static void ReplaceForDevelopment(AbpVirtualFileSystemOptions options, string physicalPath)
    {
        options.FileSets.ReplaceEmbeddedByPhysical<SampleVfsModule>(physicalPath);
    }

    internal sealed class Reader : ITransientDependency
    {
        private readonly IVirtualFileProvider _virtualFileProvider;

        public Reader(IVirtualFileProvider virtualFileProvider)
        {
            _virtualFileProvider = virtualFileProvider;
        }

        public string ReadJs()
        {
            IFileInfo file = _virtualFileProvider.GetFileInfo("/MyResources/js/test.js");
            IDirectoryContents dir = _virtualFileProvider.GetDirectoryContents("/MyResources/js");
            return file.Exists ? file.ReadAsString() : string.Empty;
        }
    }
}
