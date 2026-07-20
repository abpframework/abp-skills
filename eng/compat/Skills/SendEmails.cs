// Compile-smoke for skill: abp-runtime/send-emails
// Exercises the ABP emailing + MailKit APIs the skill teaches: IEmailSender send/queue of an
// already-rendered body with AdditionalEmailSendingArgs + EmailAttachment, the render-then-send
// flow (StandardEmailTemplates name -> ITemplateRenderer -> body), and the MailKit TLS option.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MailKit.Security;
using Volo.Abp.Emailing;
using Volo.Abp.Emailing.Templates;
using Volo.Abp.MailKit;
using Volo.Abp.TextTemplating;

namespace AbpSkillsCompat.Skills;

internal static class SendEmails
{
    // send-emails takes an already-rendered body string, not a template name.
    internal static async Task Send(IEmailSender emailSender, string renderedBody)
    {
        var args = new AdditionalEmailSendingArgs
        {
            CC = new List<string> { "cc@domain.com" },
            Attachments = new List<EmailAttachment>
            {
                new EmailAttachment { Name = "invoice.pdf", File = Array.Empty<byte>() }
            }
        };

        await emailSender.SendAsync(
            "target@domain.com", "Email subject", renderedBody, isBodyHtml: true, additionalEmailSendingArgs: args);
        await emailSender.QueueAsync("target@domain.com", "Email subject", renderedBody);
    }

    // Render-then-send: StandardEmailTemplates.Message is a template NAME for the renderer,
    // and the rendered result is the body. (Rendering itself is the render-text-templates skill.)
    internal static async Task RenderThenSend(ITemplateRenderer templateRenderer, IEmailSender emailSender)
    {
        var body = await templateRenderer.RenderAsync(
            StandardEmailTemplates.Message,
            new { message = "This is the email body..." });
        _ = StandardEmailTemplates.Layout;

        await emailSender.SendAsync("target@domain.com", "Email subject", body);
    }

    internal static void MailKitOptions(AbpMailKitOptions options)
    {
        options.SecureSocketOption = SecureSocketOptions.SslOnConnect;
    }
}
