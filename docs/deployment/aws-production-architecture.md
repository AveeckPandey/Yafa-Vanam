# YAFA VANAM AWS production architecture

This is the implementation target based on the approved AWS architecture
diagram. It replaces the earlier ECS-only proposal for the public application
tier. The application containers remain useful for consistent local builds;
the release hosts run them on private EC2 instances managed by Auto Scaling.

## Request path

`Route 53 → CloudFront → S3` serves immutable storefront assets. Dynamic
requests go from CloudFront to the public Application Load Balancer, then only
to web/API instances in private application subnets. The load balancer, ASG,
and RDS each span two availability zones. CloudFront must never cache API,
authentication, checkout, cart, or personalised responses.

## Private workloads and data

- RDS PostgreSQL Multi-AZ is the commerce system of record. Turn on automated
  backups, deletion protection, encryption, enhanced monitoring, and require
  TLS. Use a separate PostgreSQL database with `pgvector` for RAG content;
  never use the commerce schema as a vector store.
- DynamoDB provides high-volume, low-latency non-transactional reads (for
  example materialised cache records), with point-in-time
  recovery enabled.
- SQS FIFO receives order/lifecycle events. Lambda consumes messages
  idempotently and sends approved transactional messages through SES.
- Bedrock uses `amazon.titan-embed-text-v2:0` through the EC2 instance profile.
  The private RAG service supports `EMBEDDING_PROVIDER=bedrock` without
  an API key. Enable model access for the chosen region before release.
- S3 stores only static public assets behind CloudFront. EC2 instance roles use
  least-privilege bucket access; no AWS access keys are stored in application
  secrets.

## Required AWS configuration

1. Two public and four private subnets across two availability zones; use NAT
   gateways or VPC endpoints for ECR, S3, Secrets Manager, CloudWatch, SQS,
   DynamoDB, Bedrock Runtime, and SES.
2. Security groups: Internet → ALB (443 only); ALB → web/API (3000/4000);
   web → RAG service and web/API → RDS/Redis; no public inbound path to
   databases, queues, Lambda, or the RAG service.
3. Store database passwords, JWT, Razorpay keys, Cognito client secret, and
   service tokens in Secrets Manager. Give the EC2 instance profile permission
   only to read the service-specific secret ARNs.
4. ACM certificate and Route 53 aliases for the public domain. Enforce HTTPS
   and redirect HTTP at CloudFront/ALB.
5. CloudWatch logs, metrics, alarms, and rollback-ready launch-template
   versions for every Auto Scaling deployment.

## Application settings

Use `EMBEDDING_PROVIDER=bedrock`,
`EMBEDDING_MODEL=amazon.titan-embed-text-v2:0`,
`EMBEDDING_DIMENSION=1024`, and `BEDROCK_REGION=ap-south-1` for the RAG
service. Grant its instance profile `bedrock:InvokeModel` only
for the Titan embedding model ARN. Keep `VECTOR_DATABASE_URL` pointed at the
dedicated private pgvector database.

The existing welcome-coupon Lambda is already designed for Cognito
PostConfirmation and SES. Place it in private subnets only if it needs private
API access; otherwise expose the internal API through a tightly scoped private
load-balancer/VPC endpoint route rather than a public unauthenticated path.
