# YAFA VANAM production roadmap

## Launch principles

- Deploy through GitHub Actions using short-lived AWS OIDC credentials. Never
  deploy with the AWS root account or long-lived access keys.
- Keep PostgreSQL and Redis private. Only the ALB accepts public traffic.
- Treat PostgreSQL as the authority for inventory, orders, payments, and
  reviews. Product JSON remains descriptive catalogue data only.
- Use forward-only migrations, immutable image tags, health-checked rolling
  updates, budgets, alarms, and a documented rollback.
- Never present generated testimonials as customer reviews. Development sample
  reviews must display a `Sample review` label and remain disabled by default.

## Phase 1: secure delivery connection

1. Restrict the `yafa-github-deploy` trust policy to
   `AveeckPandey/Yafa-Vanam` on `main`.
2. Build and test all three containers in CI, scan them, push immutable commit
   tags, and update the Auto Scaling launch template to that exact release.
3. Keep `production` only as a convenience tag; instances must record the
   immutable commit digest used for rollback.
4. Replace hard-coded endpoints in user data with launch-template parameters or
   Secrets Manager values.

## Phase 2: production inventory

1. Seed each canonical catalogue variant into `inventory_levels`. The approved
   initial import sets all 401 active variants to 100 units and preserves an
   auditable adjustment reason.
2. Record receipts and corrections through audited inventory adjustments.
3. At order creation, lock all requested variant rows in deterministic order
   and reserve quantities in the same database transaction as the order.
4. On the first successful payment capture, convert each reservation to a sale
   exactly once. Expired unpaid reservations are released by a scheduled job.
5. Product and cart availability are advisory; checkout is the final atomic
   stock check. At 10 available units or fewer, payment capture writes a
   transactional outbox event. The API retries it to SQS, Lambda validates it,
   and SNS emails the administrator. Failed Lambda deliveries retry and then
   move to a dead-letter queue with a CloudWatch alarm.

## Phase 3: trustworthy reviews

1. Public product pages list approved reviews and aggregate ratings.
2. A signed-in customer can submit once per purchased order item. The backend
   derives product and verified-purchase status from the order; the browser
   cannot claim either value.
3. New reviews enter moderation. Rejected, deleted, or abusive content is not
   returned publicly, while moderation actions remain auditable.
4. Clearly labeled sample reviews may be enabled only for local/demo builds.
   They do not affect production rating totals or structured SEO data.

## Phase 4: AWS release

1. Validate migrations against a disposable PostgreSQL/pgvector database.
2. Back up RDS, apply migrations once under the migration advisory lock, seed
   inventory with real warehouse counts, and run catalogue/RAG reconciliation.
3. Roll out one instance, verify web/API/RAG and checkout, then continue the
   Auto Scaling refresh. Roll back on health, latency, or error alarms.
4. Configure AWS Budgets, CloudWatch alarms, retention, backup restore tests,
   WAF rate limits, TLS, and DNS before accepting real payments.

## Launch gates

- No root credentials in CI, hosts, files, or secrets.
- No sale when authoritative inventory is missing or insufficient.
- No duplicate stock deduction on payment retries or duplicate webhooks.
- No unlabeled sample review in production.
- RDS restore, application rollback, and payment webhook replay tested.
- End-to-end tests pass against the production-like database and AWS staging.
