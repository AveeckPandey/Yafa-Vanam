# Welcome-coupon Lambda (Cognito PostConfirmation)

Fires on `PostConfirmation_ConfirmSignUp`, mints the customer's single 10%
welcome coupon through the Go commerce API, emails it via SES, and records the
delivery outcome.

```
ConfirmSignUp ──▶ Cognito PostConfirmation ──▶ this Lambda
                   │  POST {GO_API_URL}/api/internal/coupons/welcome
                   │        Bearer YAFA_INTERNAL_SERVICE_TOKEN
                   │        {cognito_sub, email}
                   │     ▸ Go upserts the users row, returns existing coupon if
                   │       one exists (idempotent), else inserts
                   │       WELCOME10-<8 chars>, max_uses=1, 30-day expiry.
                   │       One-per-user is a DB constraint (partial unique index).
                   ├─▶ SES SendEmail (code + terms only — no internal ids)
                   └─▶ POST /api/internal/messages/record → lifecycle_messages
```

## Why the Lambda calls Go instead of writing SQL

Railway's Postgres is private-network only — unreachable from Lambda. The API
stays the sole database writer and reuses its existing service-token pattern.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `GO_API_URL` | yes | e.g. `https://api.yafavanam.com` |
| `YAFA_INTERNAL_SERVICE_TOKEN` | yes | must equal the API's value |
| `SES_FROM` | yes | DKIM-verified identity, e.g. `YAFA VANAM <hello@yafavanam.com>` |
| `SES_REGION` | no | defaults to `ap-south-1` |
| `SES_CONFIGURATION_SET` | no | SES v2 configuration set |

## Deploy

```bash
export AWS_REGION=ap-south-1 COGNITO_USER_POOL_ID=ap-south-1_XXXX GO_API_URL=https://api.yafavanam.com \
       YAFA_INTERNAL_SERVICE_TOKEN=... 'SES_FROM=YAFA VANAM <hello@yafavanam.com>'
./deploy.sh
```

The script creates/updates the function (Node 22, arm64), attaches a
least-privilege inline policy (logs for this function + `ses:SendEmail` on
`yafavanam.com` only), grants Cognito invoke permission scoped to the pool ARN,
and sets the pool's `PostConfirmation` lambda config.

## Failure semantics

- **Coupon issue fails** → handler throws; CloudWatch alarm fires. The account
  is already confirmed — the customer signs in as normal; replay by re-running
  the issue call manually with the customer's email.
- **Email fails** → sign-up still succeeds. Coupon stays valid; the attempt is
  recorded in `lifecycle_messages` with status `FAILED` for ops replay.
- **Retries / duplicate triggers** → the issue endpoint returns the same
  existing coupon; no duplicate codes or emails can be minted server-side.

## Privacy

Logs contain statuses and message ids only. Never log emails, coupon codes, or
Cognito subjects; emails never contain internal identifiers.
