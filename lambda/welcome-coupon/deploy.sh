#!/usr/bin/env bash
# Deploys the welcome-coupon Lambda and wires it as the Cognito PostConfirmation
# trigger. Run once per environment after `aws login` / profile selection.
#
# Required environment variables:
#   AWS_REGION              e.g. ap-south-1 (pool + Lambda + SES all live here)
#   COGNITO_USER_POOL_ID    e.g. ap-south-1_XXXXXXXXX
#   GO_API_URL              e.g. https://api.yafavanam.com  (no trailing slash)
#   YAFA_INTERNAL_SERVICE_TOKEN  must match the API's YAFA_INTERNAL_SERVICE_TOKEN
#   SES_FROM                e.g. "YAFA VANAM <hello@yafavanam.com>" (DKIM-verified)
#
# Optional:
#   LAMBDA_NAME             default yafa-welcome-coupon
#   SES_CONFIGURATION_SET   SES v2 configuration set name
set -euo pipefail

: "${AWS_REGION:?set AWS_REGION}" "${COGNITO_USER_POOL_ID:?set COGNITO_USER_POOL_ID}" \
  "${GO_API_URL:?set GO_API_URL}" "${YAFA_INTERNAL_SERVICE_TOKEN:?set YAFA_INTERNAL_SERVICE_TOKEN}" \
  "${SES_FROM:?set SES_FROM}"
LAMBDA_NAME="${LAMBDA_NAME:-yafa-welcome-coupon}"
ROLE_NAME="${ROLE_NAME:-yafa-welcome-coupon-lambda}"
RUNTIME="nodejs22.x"
here="$(cd "$(dirname "$0")" && pwd)"

echo "== Packaging =="
work="$(mktemp -d)"
cp "$here/index.mjs" "$work/"
(cd "$work" && zip -q function.zip index.mjs)

echo "== Ensuring IAM role ($ROLE_NAME) =="
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
  }' >/dev/null
fi
# Least-privilege inline policy: logs + sending from the verified identity only.
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name yafa-welcome-coupon --policy-document "$(cat <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID:-*}:log-group:/aws/lambda/${LAMBDA_NAME}:*"
    },
    {
      "Sid": "SendWelcomeEmail",
      "Effect": "Allow",
      "Action": "ses:SendEmail",
      "Resource": "arn:aws:ses:${AWS_REGION}:${ACCOUNT_ID:-*}:identity/yafavanam.com"
    }
  ]
}
POLICY
)"

echo "== Deploying function ($LAMBDA_NAME) =="
if aws lambda get-function --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$LAMBDA_NAME" --zip-file "fileb://$work/function.zip" >/dev/null
  aws lambda wait function-updated --function-name "$LAMBDA_NAME"
else
  aws lambda create-function \
    --function-name "$LAMBDA_NAME" \
    --runtime "$RUNTIME" \
    --architectures arm64 \
    --handler index.handler \
    --role "arn:aws:iam::${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}:role/$ROLE_NAME" \
    --zip-file "fileb://$work/function.zip" \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={GO_API_URL=$GO_API_URL,YAFA_INTERNAL_SERVICE_TOKEN=$YAFA_INTERNAL_SERVICE_TOKEN,SES_FROM=$SES_FROM,SES_REGION=$AWS_REGION${CONFIGURATION_SET:+,SES_CONFIGURATION_SET=$CONFIGURATION_SET}}" \
    >/dev/null
  aws lambda wait function-active --function-name "$LAMBDA_NAME"
fi

echo "== Allowing Cognito to invoke the function =="
aws lambda add-permission \
  --function-name "$LAMBDA_NAME" \
  --statement-id yafa-post-confirmation \
  --action lambda:InvokeFunction \
  --principal cognito-idp.amazonaws.com \
  --source-arn "arn:aws:cognito-idp:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):userpool/${COGNITO_USER_POOL_ID}" \
  >/dev/null 2>&1 || echo "(permission already present)"

echo "== Attaching PostConfirmation trigger to the pool =="
aws cognito-idp update-user-pool --region "$AWS_REGION" --user-pool-id "$COGNITO_USER_POOL_ID" \
  --lambda-config "PostConfirmation=arn:aws:lambda:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):function:$LAMBDA_NAME"

echo "Done. Smoke test with a real sign-up through the storefront."
