// Compile-smoke for skill: abp-runtime/send-sms
// Exercises the ABP ISmsSender / SmsMessage abstraction the skill teaches.
using System.Collections.Generic;
using System.Threading.Tasks;
using Volo.Abp.Modularity;
using Volo.Abp.Sms;

namespace AbpSkillsCompat.Skills;

[DependsOn(typeof(AbpSmsModule))]
internal class NotificationsModule : AbpModule
{
}

internal static class SendSms
{
    internal static async Task SendSimple(ISmsSender smsSender, string phoneNumber, string code)
    {
        // Extension overload
        await smsSender.SendAsync(phoneNumber, $"Your verification code is {code}");
    }

    internal static async Task SendWithProperties(ISmsSender smsSender, string phoneNumber, string text, string templateCode)
    {
        var message = new SmsMessage(phoneNumber, text);
        IDictionary<string, object> properties = message.Properties;
        properties["TemplateCode"] = templateCode;

        string number = message.PhoneNumber;
        string body = message.Text;

        await smsSender.SendAsync(message);
    }
}
