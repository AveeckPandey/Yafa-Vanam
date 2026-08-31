#!/bin/bash
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
PROJECT_NAME="${PROJECT_NAME:-yafa-prod}"
ARTIFACT_URI="${1:?usage: validate-migrations-on-ec2.sh s3://bucket/migrations.zip}"
WORK_DIR=$(mktemp -d /tmp/yafa-migration-validation.XXXXXX)
TEST_DATABASE="yafa_migration_validation_$(date +%s)"
DB_HOST=""
DB_USER=""
DB_PASSWORD=""

run_psql() {
  docker run --rm \
    -e PGHOST="$DB_HOST" -e PGPORT=5432 -e PGUSER="$DB_USER" \
    -e PGPASSWORD="$DB_PASSWORD" -e PGSSLMODE=require \
    -v "$WORK_DIR/migrations:/migrations:ro" \
    postgres:16-alpine psql "$@"
}

cleanup() {
  if [[ -n "$DB_HOST" && -n "$DB_USER" && -n "$DB_PASSWORD" ]]; then
    run_psql --dbname postgres --set ON_ERROR_STOP=1 \
      --command "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${TEST_DATABASE}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    run_psql --dbname postgres --set ON_ERROR_STOP=1 \
      --command "DROP DATABASE IF EXISTS ${TEST_DATABASE};" >/dev/null 2>&1 || true
  fi
  case "$WORK_DIR" in
    /tmp/yafa-migration-validation.*) rm -rf -- "$WORK_DIR" ;;
  esac
}
trap cleanup EXIT

DB_SECRET_ARN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "${PROJECT_NAME}-data" --query "Stacks[0].Outputs[?OutputKey=='DatabaseMasterSecretArn'].OutputValue" --output text)
DB_HOST=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "${PROJECT_NAME}-data" --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" --output text)
DB_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$DB_SECRET_ARN" --query SecretString --output text)
DB_USER=$(jq -r .username <<< "$DB_JSON")
DB_PASSWORD=$(jq -r .password <<< "$DB_JSON")

aws s3 cp "$ARTIFACT_URI" "$WORK_DIR/migrations.zip" --region "$REGION" --only-show-errors
python3 -c 'import pathlib, sys, zipfile; target=pathlib.Path(sys.argv[2]); target.mkdir(); zipfile.ZipFile(sys.argv[1]).extractall(target)' "$WORK_DIR/migrations.zip" "$WORK_DIR/migrations"

docker pull postgres:16-alpine >/dev/null
run_psql --dbname postgres --set ON_ERROR_STOP=1 --command "CREATE DATABASE ${TEST_DATABASE};" >/dev/null

while IFS= read -r migration; do
  filename=$(basename "$migration")
  echo "Applying ${filename}"
  run_psql --dbname "$TEST_DATABASE" --set ON_ERROR_STOP=1 --single-transaction --file "/migrations/${filename}" >/dev/null
done < <(find "$WORK_DIR/migrations" -maxdepth 1 -type f -name '*.sql' | sort)

run_psql --dbname "$TEST_DATABASE" --tuples-only --no-align --set ON_ERROR_STOP=1 \
  --command "SELECT CASE WHEN to_regclass('inventory_levels') IS NOT NULL AND to_regclass('inventory_alert_outbox') IS NOT NULL AND to_regclass('product_reviews') IS NOT NULL THEN 'migration-validation-ok' ELSE 'migration-validation-failed' END;"
