# AWS ECS deployment (alternative)

> The approved production topology is now the EC2 Auto Scaling architecture in
> [AWS production architecture](aws-production-architecture.md). Keep this
> document only as an ECS container deployment alternative.

This release runs the storefront, commerce API, and private RAG service as
separate ECS Fargate services. It is deliberately not a lift-and-shift of the
old Railway/Vercel instructions: the RAG service remains reachable
only from the web/API security groups, and all credentials are stored in AWS
Secrets Manager.

## Target architecture

| Component | AWS service | Public? |
| --- | --- | --- |
| Storefront | ECS Fargate behind an Application Load Balancer | Yes |
| Commerce API | ECS Fargate behind the same Application Load Balancer at `/api/v1/*` | Yes, only through the load balancer |
| Product-knowledge RAG | ECS Fargate + Cloud Map service discovery | No |
| Commerce data | RDS PostgreSQL 16 (Multi-AZ in production) | No |
| Sessions/rate limits | ElastiCache Redis 7 | No |
| Customer identity | Amazon Cognito User Pool | Yes, through the storefront |
| TLS and DNS | ACM certificate + Route 53 alias record | Yes |

The ALB routes `/api/v1/*` to the Go API. Next.js handles its own `/api/*`
route handlers, including the server-only Yafa RAG bridge. Set `YAFA_RAG_URL` to
the RAG service's Cloud Map DNS name; never expose it as a public
environment variable.

## Before the first release

1. Install AWS CLI v2 and authenticate with a least-privilege IAM role in the
   intended AWS account. Use `ap-south-1` unless you have chosen another region.
2. Create a VPC spanning at least two availability zones, with public subnets
   for the load balancer and private subnets for Fargate, RDS, and Redis. Give
   private tasks outbound access through a NAT gateway or VPC endpoints for ECR,
   CloudWatch Logs, Secrets Manager, and S3.
3. Create the PostgreSQL database and Redis replication group. Enforce TLS from
   ECS to both services and allow inbound traffic only from the API task security
   group.
4. Create an ACM certificate in the ALB region and validate the `yafavanam.com`
   DNS name. Point Route 53 aliases for the apex (and optional `www`) at the ALB.
5. Create the Cognito User Pool/client and copy its values into the `web`
   secret. The client secret belongs only in the web task.

## Secrets Manager values

Create three JSON secrets, one per service. Give each ECS task role access only
to its own secret. Do not place values in task definitions, shell history, or
source control.

`yafa/prod/web`

```json
{
  "COMMERCE_API_URL": "http://yafa-api.yafa.local:4000",
  "YAFA_RAG_URL": "http://yafa-rag.yafa.local:8000",
  "YAFA_INTERNAL_SERVICE_TOKEN": "<same-random-32-plus-character-token>",
  "COGNITO_REGION": "ap-south-1",
  "COGNITO_USER_POOL_ID": "<pool-id>",
  "COGNITO_CLIENT_ID": "<client-id>",
  "COGNITO_CLIENT_SECRET": "<client-secret>",
  "COGNITO_REFRESH_USERNAME_SOURCE": "username_claim"
}
```

`yafa/prod/api`

```json
{
  "DATABASE_URL": "postgresql://<user>:<password>@<rds-endpoint>:5432/yafa_vanam?sslmode=require",
  "REDIS_URL": "rediss://<elasticache-endpoint>:6379/0",
  "JWT_SECRET": "<random-32-plus-character-secret>",
  "YAFA_INTERNAL_SERVICE_TOKEN": "<same-random-32-plus-character-token>",
  "RAZORPAY_KEY_ID": "<live-key-id>",
  "RAZORPAY_KEY_SECRET": "<live-key-secret>",
  "RAZORPAY_WEBHOOK_SECRET": "<webhook-secret>"
}
```

`yafa/prod/rag` must contain `YAFA_INTERNAL_SERVICE_TOKEN`,
`VECTOR_DATABASE_URL`, and the selected embedding-provider settings.

Set the following non-secret environment values in the API task definition:
`APP_ENV=production`, `ENVIRONMENT=production`, `API_PORT=4000`,
`APP_URL=https://yafavanam.com`,
`CORS_ALLOWED_ORIGINS=https://yafavanam.com,https://www.yafavanam.com`,
`MIGRATIONS_PATH=/app/db/migrations`, and `RAZORPAY_CHECKOUT_ENABLED=true`.

## Images and ECS health checks

Build all images from the repository root so the monorepo paths resolve:

```powershell
docker build -f apps/web/Dockerfile -t yafa-web:release .
docker build -f apps/api/Dockerfile -t yafa-api:release .
docker build -f services/recommendation-engine/Dockerfile -t yafa-rag:release .
```

Create private ECR repositories for `yafa-web`, `yafa-api`, and `yafa-rag`.
Use immutable image tags (the Git commit SHA) and deploy the same digest that
passed CI. Configure ECS health checks as follows:

- web: `GET /` on port 3000;
- API: `GET /ready` on port 4000;
- RAG: `GET /health` on port 8000.

Use at least two tasks for web and API in production, enable ECS deployment
circuit breakers with rollback, and stream all task logs to separate CloudWatch
log groups with retention enabled.

## Release checklist

1. Push the three immutable images to ECR and update the ECS task definitions.
2. Deploy the RAG service, then API, then web services. The Go API automatically
   runs forward-only database migrations during startup under an advisory lock.
3. Verify `https://yafavanam.com/`, `https://<api-domain>/health`, and
   `https://<api-domain>/ready`.
4. Set the Razorpay webhook to
   `https://<api-domain>/api/v1/payments/razorpay/webhook`, complete a test
   payment, and confirm the signature and webhook update.
5. Confirm the S3 bucket cannot be listed or read anonymously, the RAG service has
   no public listener, and CloudWatch logs contain no secret values.

Rollback application code by redeploying the prior ECS task-definition revision.
Do not roll back an applied database migration by deleting data; ship a reviewed
forward-fix migration or restore a verified snapshot.
