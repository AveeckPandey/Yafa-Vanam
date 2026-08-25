// Welcome-coupon trigger — Cognito PostConfirmation_ConfirmSignUp.
//
// Flow: confirmed sign-up -> issue coupon via the Go commerce API (idempotent,
// one per user enforced server-side) -> SES welcome email containing ONLY the
// code and its terms -> record the delivery outcome for auditing.
//
// Failure policy (matches the product spec):
//   - Coupon issue failing is serious enough to surface: the handler throws so
//     CloudWatch alarms fire. The customer's account is already confirmed at
//     this point, so they simply sign in later; support can replay the event.
//   - Email failures NEVER fail sign-up. The coupon stays valid in the
//     database, the attempt is recorded as FAILED, and the handler returns
//     the event successfully.
//
// Privacy: logs carry statuses and message ids only — never email addresses,
// coupon codes, or Cognito subject identifiers. Emails contain no internal
// identifiers either.

import { SendEmailCommand, SESv2Client } from "@aws-sdk/client-sesv2";

const GO_API_URL = requireEnv("GO_API_URL");
const SERVICE_TOKEN = requireEnv("YAFA_INTERNAL_SERVICE_TOKEN");
const SES_FROM = requireEnv("SES_FROM");
const SES_REGION = process.env.SES_REGION || "ap-south-1";
const CONFIGURATION_SET = process.env.SES_CONFIGURATION_SET || undefined;

const ses = new SESv2Client({ region: SES_REGION });
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export const handler = async (event) => {
  // Other trigger sources (PreSignUp, PostAuthentication, ...) pass through untouched.
  if (event?.triggerSource !== "PostConfirmation_ConfirmSignUp") return event;
  const attributes = event.request?.userAttributes ?? {};
  const subject = typeof attributes.sub === "string" ? attributes.sub : "";
  const email = typeof attributes.email === "string" ? attributes.email.trim().toLowerCase() : "";
  // Malformed payloads must never block a real confirmation — ignore quietly.
  if (!subject || subject.length > 128 || !EMAIL_PATTERN.test(email) || email.length > 254) {
    console.warn(JSON.stringify({ msg: "welcome_coupon_skipped_invalid_event" }));
    return event;
  }

  const coupon = await issueCoupon(subject, email);

  try {
    const messageId = await sendWelcomeEmail(email, coupon);
    await recordOutcome({ email, couponCode: coupon.code, providerMessageId: messageId, status: "SENT" });
    console.log(JSON.stringify({ msg: "welcome_coupon_delivered", provider_message_id: messageId }));
  } catch (error) {
    // Email problems keep the coupon and never fail the sign-up.
    console.warn(JSON.stringify({ msg: "welcome_email_failed", reason: error?.name || "unknown" }));
    await recordOutcome({ email, couponCode: coupon.code, providerMessageId: "", status: "FAILED" }).catch(() => undefined);
  }
  return event;
};

async function issueCoupon(subject, email) {
  const coupon = await callGoApi("/api/internal/coupons/welcome", { cognito_sub: subject, email }, { attempts: 3 });
  return { code: String(coupon.code), expiresAt: coupon.expires_at };
}

async function recordOutcome({ email, couponCode, providerMessageId, status }) {
  await callGoApi(
    "/api/internal/messages/record",
    {
      email,
      channel: "EMAIL",
      trigger_name: "welcome_coupon",
      template_name: "welcome-coupon-v1",
      coupon_code: couponCode,
      provider_message_id: providerMessageId,
      status,
    },
    { attempts: 2 },
  );
}

async function callGoApi(path, body, { attempts }) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt++) {
    if (attempt > 0) await sleep(250 * 2 ** (attempt - 1));
    try {
      const response = await fetch(`${GO_API_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${SERVICE_TOKEN}` },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(8_000),
      });
      if (response.ok) return response.json();
      // 4xx from our own API means the request itself is bad — retrying cannot help.
      if (response.status >= 400 && response.status < 500) {
        throw new Error(`go_api_client_error_${response.status}`);
      }
      lastError = new Error(`go_api_server_error_${response.status}`);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError ?? new Error("go_api_unreachable");
}

async function sendWelcomeEmail(email, coupon) {
  const expiry = new Date(coupon.expiresAt);
  const expiryText = Number.isNaN(expiry.getTime())
    ? "in 30 days"
    : expiry.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
  const result = await ses.send(new SendEmailCommand({
    FromEmailAddress: SES_FROM,
    ...(CONFIGURATION_SET ? { ConfigurationSetName: CONFIGURATION_SET } : {}),
    Destination: { ToAddresses: [email] },
    Content: {
      Simple: {
        Subject: { Data: "Welcome to YAFA VANAM — your 10% off is inside", Charset: "UTF-8" },
        Body: {
          Html: { Data: welcomeEmailHtml(coupon.code, expiryText), Charset: "UTF-8" },
          Text: { Data: welcomeEmailText(coupon.code, expiryText), Charset: "UTF-8" },
        },
      },
    },
  }));
  return result.MessageId ?? "";
}

function welcomeEmailHtml(code, expiryText) {
  const escaped = code.replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
  return `<!doctype html><html><body style="margin:0;padding:0;background:#faf5f6;font-family:Georgia,'Times New Roman',serif;color:#2c2c2c">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:520px;background:#fcf9fa;border-radius:22px;padding:40px">
<tr><td style="color:#a66b7b;font-size:11px;font-weight:bold;letter-spacing:.16em">YAFA VANAM</td></tr>
<tr><td style="padding-top:14px;font-size:30px;line-height:1.1">Welcome to the ritual.</td></tr>
<tr><td style="padding-top:14px;font-size:14px;line-height:1.6;color:#5f5a57">Your account is ready. As a thank-you, here is <strong>10% off</strong> your first order.</td></tr>
<tr><td align="center" style="padding:26px 0"><div style="display:inline-block;border:1px solid #111;border-radius:10px;background:#111;color:#ffffff;font-family:Arial,sans-serif;font-size:20px;font-weight:bold;letter-spacing:.12em;padding:16px 28px">${escaped}</div></td></tr>
<tr><td align="center" style="font-size:12px;color:#5f5a57;font-family:Arial,sans-serif">Valid until ${expiryText} &middot; One use per account &middot; Applies at checkout</td></tr>
<tr><td style="padding-top:26px;border-top:1px solid #ddcbd0;font-size:11px;line-height:1.6;color:#9a9189;font-family:Arial,sans-serif">You received this email because you created a YAFA VANAM account. If this wasn't you, you can safely ignore it.</td></tr>
</table></td></tr></table></body></html>`;
}

function welcomeEmailText(code, expiryText) {
  return [
    "Welcome to YAFA VANAM.",
    "",
    "Your account is ready. Enjoy 10% off your first order with this code:",
    "",
    `    ${code}`,
    "",
    `Valid until ${expiryText}. One use per account; apply it at checkout.`,
    "",
    "You received this email because you created a YAFA VANAM account.",
  ].join("\n");
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`missing_required_env_${name}`);
  return value;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
