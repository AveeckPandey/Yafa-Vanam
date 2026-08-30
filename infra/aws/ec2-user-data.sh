#!/bin/bash
set -euo pipefail
REGION=ap-south-1
REGISTRY=758388043025.dkr.ecr.ap-south-1.amazonaws.com
RUNTIME_SECRET_ARN=arn:aws:secretsmanager:ap-south-1:758388043025:secret:yafa/prod/runtime-GDcXI8
RAZORPAY_SECRET_ARN=arn:aws:secretsmanager:ap-south-1:758388043025:secret:yafa/prod/razorpay-test-fNcL3V
COGNITO_SECRET_ARN=arn:aws:secretsmanager:ap-south-1:758388043025:secret:yafa/prod/cognito-KZu84k
DB_SECRET_ARN=arn:aws:secretsmanager:ap-south-1:758388043025:secret:rds!db-3d5bfe9c-aa13-46ae-add5-08c6496868c2-Pgm77y
DB_HOST=yafa-prod-commerce.c9cwecyc0ivr.ap-south-1.rds.amazonaws.com
REDIS_HOST=master.yafa-prod-redis.723sn5.aps1.cache.amazonaws.com

dnf install -y docker jq awscli
systemctl enable --now docker
TOKEN=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$RUNTIME_SECRET_ARN" --query SecretString --output text)
DB_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$DB_SECRET_ARN" --query SecretString --output text)
DB_USER=$(jq -r .username <<< "$DB_JSON")
DB_PASSWORD=$(jq -r .password <<< "$DB_JSON")
RAZORPAY_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$RAZORPAY_SECRET_ARN" --query SecretString --output text)
RAZORPAY_KEY_ID=$(jq -r .key_id <<< "$RAZORPAY_JSON")
RAZORPAY_KEY_SECRET=$(jq -r .key_secret <<< "$RAZORPAY_JSON")
RAZORPAY_WEBHOOK_SECRET=$(jq -r .webhook_secret <<< "$RAZORPAY_JSON")
COGNITO_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$COGNITO_SECRET_ARN" --query SecretString --output text)
COGNITO_REGION=$(jq -r .region <<< "$COGNITO_JSON")
COGNITO_USER_POOL_ID=$(jq -r .user_pool_id <<< "$COGNITO_JSON")
COGNITO_CLIENT_ID=$(jq -r .client_id <<< "$COGNITO_JSON")
COGNITO_CLIENT_SECRET=$(jq -r .client_secret <<< "$COGNITO_JSON")
COGNITO_REFRESH_USERNAME_SOURCE=$(jq -r .refresh_username_source <<< "$COGNITO_JSON")
# Database passwords may include characters that have a special meaning in a
# connection URL. Encode them before constructing DATABASE_URL.
DB_PASSWORD_ENCODED=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip(), safe=""))' <<< "$DB_PASSWORD")
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

docker run -d --name yafa-rag --restart unless-stopped --network host \
  -e AWS_REGION="$REGION" -e AWS_DEFAULT_REGION="$REGION" \
  -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e VECTOR_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENCODED}@${DB_HOST}:5432/yafa_rag?sslmode=require" \
  -e EMBEDDING_PROVIDER=bedrock -e EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
  -e EMBEDDING_DIMENSION=1024 -e BEDROCK_REGION="$REGION" \
  -e RAG_RERANK_ENABLED=false \
  "$REGISTRY/yafa-advisor:production"
docker run -d --name yafa-api --restart unless-stopped --network host \
  -e APP_ENV=production -e ENVIRONMENT=production -e API_PORT=4000 \
  -e AWS_REGION="$REGION" -e AWS_DEFAULT_REGION="$REGION" \
  -e APP_URL=https://yafavanam.buildwithaveeck.com \
  -e CORS_ALLOWED_ORIGINS=https://yafavanam.buildwithaveeck.com \
  -e DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENCODED}@${DB_HOST}:5432/yafa_vanam?sslmode=require" \
  -e REDIS_URL="rediss://${REDIS_HOST}:6379/0" -e JWT_SECRET="$TOKEN" \
  -e RAZORPAY_CHECKOUT_ENABLED=true -e RAZORPAY_KEY_ID="$RAZORPAY_KEY_ID" \
  -e RAZORPAY_KEY_SECRET="$RAZORPAY_KEY_SECRET" -e RAZORPAY_WEBHOOK_SECRET="$RAZORPAY_WEBHOOK_SECRET" \
	-e ORDER_CONFIRMATION_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/758388043025/yafa-prod-order-confirmations \
  -e YAFA_STORAGE_REGION="$REGION" -e YAFA_STORAGE_BUCKET=yafa-prod-selfies-758388043025-ap-south-1 \
  -e YAFA_ANALYZER_URL=http://127.0.0.1:8000 -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e COGNITO_REGION="$COGNITO_REGION" -e COGNITO_USER_POOL_ID="$COGNITO_USER_POOL_ID" \
  -e COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" \
  "$REGISTRY/yafa-api:production"
docker run -d --name yafa-web --restart unless-stopped --network host \
  -e PORT=3000 -e COMMERCE_API_URL=http://127.0.0.1:4000 \
  -e YAFA_RAG_URL=http://127.0.0.1:8000 -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e COGNITO_REGION="$COGNITO_REGION" -e COGNITO_USER_POOL_ID="$COGNITO_USER_POOL_ID" \
  -e COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" -e COGNITO_CLIENT_SECRET="$COGNITO_CLIENT_SECRET" \
  -e COGNITO_REFRESH_USERNAME_SOURCE="$COGNITO_REFRESH_USERNAME_SOURCE" \
  "$REGISTRY/yafa-web:production"
