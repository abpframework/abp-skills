using Volo.Abp.Security.Encryption;

namespace AbpSkillsCompat.Skills;

internal static class EncryptStrings
{
    internal static void Service(IStringEncryptionService encryptionService, string passPhrase, byte[] salt)
    {
        string? cipher = encryptionService.Encrypt("plain");
        string? plain = encryptionService.Decrypt(cipher);
        string? withArgs = encryptionService.Encrypt("plain", passPhrase, salt);
    }

    internal static void Options(AbpStringEncryptionOptions options, string passPhrase, byte[] initVector, byte[] salt)
    {
        options.Keysize = 256;
        options.DefaultPassPhrase = passPhrase;
        options.InitVectorBytes = initVector;
        options.DefaultSalt = salt;
    }
}
