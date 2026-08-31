#!/bin/bash
set -euo pipefail
REGION=ap-south-1
PROJECT_NAME=yafa-prod
IMAGE_TAG=production
dnf install -y docker jq awscli
systemctl enable --now docker

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
RUNTIME_SECRET_ARN="yafa/prod/runtime"
RAZORPAY_SECRET_ARN="yafa/prod/razorpay-test"
COGNITO_SECRET_ARN="yafa/prod/cognito"
DB_SECRET_ARN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "${PROJECT_NAME}-data" --query "Stacks[0].Outputs[?OutputKey=='DatabaseMasterSecretArn'].OutputValue" --output text)
DB_HOST=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "${PROJECT_NAME}-data" --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" --output text)
REDIS_HOST=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "${PROJECT_NAME}-data" --query "Stacks[0].Outputs[?OutputKey=='RedisPrimaryEndpoint'].OutputValue" --output text)
ORDER_QUEUE_URL=$(aws sqs get-queue-url --region "$REGION" --queue-name "${PROJECT_NAME}-order-confirmations" --query QueueUrl --output text)
INVENTORY_ALERT_QUEUE_URL=$(aws sqs get-queue-url --region "$REGION" --queue-name "${PROJECT_NAME}-inventory-alerts.fifo" --query QueueUrl --output text)
STORAGE_BUCKET="${PROJECT_NAME}-selfies-${ACCOUNT_ID}-${REGION}"

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
  -e APP_ENV=production -e ENVIRONMENT=production \
  -e AWS_REGION="$REGION" -e AWS_DEFAULT_REGION="$REGION" \
  -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e VECTOR_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENCODED}@${DB_HOST}:5432/yafa_rag?sslmode=require" \
  -e EMBEDDING_PROVIDER=bedrock -e EMBEDDING_MODEL=amazon.titan-embed-text-v2:0 \
  -e EMBEDDING_DIMENSION=1024 -e BEDROCK_REGION="$REGION" \
  -e RAG_RERANK_ENABLED=false -e RAG_CACHE_TTL_SECONDS=90 \
  -e RAG_MAX_CONCURRENT_EMBEDDINGS=8 -e RAG_QUERY_TIMEOUT_SECONDS=8 \
  -e RAG_MIN_GROUNDING_SIMILARITY=0.62 -e RAG_MAX_CONTEXT_CHARS=6000 \
  -e RAG_CIRCUIT_BREAKER_FAILURES=4 -e RAG_CIRCUIT_BREAKER_RESET_SECONDS=20 \
  -e YAFA_AGENTIC_RAG_ENABLED=true \
  -e YAFA_AGENT_MODEL=amazon.nova-lite-v1:0 -e YAFA_AGENT_MAX_TOOL_CALLS=2 \
  -e YAFA_AGENT_TIMEOUT_SECONDS=12 -e YAFA_AGENT_MAX_OUTPUT_TOKENS=350 \
  "$REGISTRY/yafa-advisor:$IMAGE_TAG"
# Reconcile the versioned catalogue on every immutable rollout. PostgreSQL's
# advisory lock serializes this when several Auto Scaling instances boot.
docker exec yafa-rag python scripts/ingest_products.py
docker run -d --name yafa-api --restart unless-stopped --network host \
  -e APP_ENV=production -e ENVIRONMENT=production -e API_PORT=4000 \
  -e AWS_REGION="$REGION" -e AWS_DEFAULT_REGION="$REGION" \
  -e APP_URL=https://yafavanam.buildwithaveeck.com \
  -e CORS_ALLOWED_ORIGINS=https://yafavanam.buildwithaveeck.com \
  -e DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD_ENCODED}@${DB_HOST}:5432/yafa_vanam?sslmode=require" \
  -e REDIS_URL="rediss://${REDIS_HOST}:6379/0" -e JWT_SECRET="$TOKEN" \
  -e RAZORPAY_CHECKOUT_ENABLED=true -e RAZORPAY_KEY_ID="$RAZORPAY_KEY_ID" \
  -e RAZORPAY_KEY_SECRET="$RAZORPAY_KEY_SECRET" -e RAZORPAY_WEBHOOK_SECRET="$RAZORPAY_WEBHOOK_SECRET" \
  -e ORDER_CONFIRMATION_QUEUE_URL="$ORDER_QUEUE_URL" \
  -e INVENTORY_ALERT_QUEUE_URL="$INVENTORY_ALERT_QUEUE_URL" \
  -e YAFA_STORAGE_REGION="$REGION" -e YAFA_STORAGE_BUCKET="$STORAGE_BUCKET" \
  -e YAFA_ANALYZER_URL=http://127.0.0.1:8000 -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e COGNITO_REGION="$COGNITO_REGION" -e COGNITO_USER_POOL_ID="$COGNITO_USER_POOL_ID" \
  -e COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" \
  "$REGISTRY/yafa-api:$IMAGE_TAG"
docker run -d --name yafa-web --restart unless-stopped --network host \
  -e PORT=3000 -e COMMERCE_API_URL=http://127.0.0.1:4000 \
  -e YAFA_RAG_URL=http://127.0.0.1:8000 -e YAFA_INTERNAL_SERVICE_TOKEN="$TOKEN" \
  -e COGNITO_REGION="$COGNITO_REGION" -e COGNITO_USER_POOL_ID="$COGNITO_USER_POOL_ID" \
  -e COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" -e COGNITO_CLIENT_SECRET="$COGNITO_CLIENT_SECRET" \
  -e COGNITO_REFRESH_USERNAME_SOURCE="$COGNITO_REFRESH_USERNAME_SOURCE" \
  "$REGISTRY/yafa-web:$IMAGE_TAG"
