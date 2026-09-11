# YAFA VANAM production RAG implementation

## Purpose and boundary

YAFA is a private, evidence-first assistant for approved YAFA VANAM product and
brand knowledge: ingredients, benefits, use, warnings, scent, and policy facts.
It is not the authority for price, stock, promotions, carts, orders, payments,
refunds, delivery estimates, medical diagnosis, or personalised shade selection.
The Go commerce API owns changing transactional facts; the Python RAG service
only explains approved, versioned knowledge.

This distinction is deliberate. Vector search can explain what a product
contains or how it should be used. It must not guess whether it is available
right now or whether a payment succeeded.

## Current implementation

| Concern | YAFA implementation | Production rule |
| --- | --- | --- |
| Sources | data/processed/Product.json and BrandKnowledge.json | Only owner-approved, versioned content is ingested. |
| Ingestion | services/recommendation-engine/app/rag/ingestion.py | Validate, chunk, hash, embed changed content, reconcile removals, audit. |
| Vector store | Dedicated PostgreSQL plus pgvector | It is never the commerce database. |
| Retrieval | app/rag/retriever.py | Alias/PDP scope, tenant and metadata filters, vector search, safety checks. |
| Generation | app/yafa/orchestrator.py and app/yafa/agent.py | Use verified evidence only; deterministic composition is the fallback. |
| Security | Private API, HMAC tenant identity, PostgreSQL RLS | Browser never receives RAG credentials or Bedrock access. |
| Monitoring | app/rag/telemetry.py, feedback API, evaluation scripts | Trace quality, safety, latency, and cost per request. |

The production path is private AWS networking:

~~~text
Browser -> Next.js server-side bridge -> private FastAPI RAG service
        -> dedicated pgvector database and Amazon Bedrock
~~~

The RAG service has no public listener. The browser has no database, Bedrock,
or service token access.

## Query path

~~~text
Customer question and optional product-page context
                    |
                    v
Next.js server-side bridge: validates session and service identity
                    |
                    v
Yafa orchestration
  live-commerce intent? ----> defer to commerce system of record
  product/brand fact? -------> choose fact types and product-page scope
                    |
                    v
Retriever
  alias resolution -> tenant/metadata filter -> vector search -> score floor
  -> customer claim policy -> injection rejection -> conflict selection
                    |
                    v
At most four compact evidence chunks
                    |
          +---------+----------+
          |                    |
          v                    v
Deterministic composition  Optional Bedrock agent: temperature 0,
                            max two read-only search calls, citations required
          |                    |
          +---------+----------+
                    v
Grounded answer, source metadata, and privacy-safe request trace
~~~

The system fails closed. If evidence is absent, weak, unsafe, contradictory,
revoked, outside the tenant, or unsupported by valid citations, YAFA says it
cannot confirm the fact instead of guessing.

## Ingestion and document lifecycle

1. Validate sources before they become searchable. The catalogue validator
   rejects malformed or duplicate product records. New source connectors should
   also use staging/quarantine, schema and ownership checks, extraction-quality
   checks, malware checks where applicable, and approval before promotion.

2. Build semantic chunks, not arbitrary paragraph slices. Typical chunk types
   are ingredients, benefits, usage, warnings, scent, and policy facts. Every
   chunk carries trust level, customer eligibility, source version, tenant ID,
   and a claim key such as yv-frag-010:scent:primary.

3. Use a stable identity derived from product, chunk type/local key, source
   version, tenant, and normalized content hash. Unchanged chunks reuse their
   existing embedding, making re-ingestion idempotent and inexpensive.

4. Embed changed chunks with the configured embedding space. Production uses
   Titan Text Embeddings V2 at 1024 dimensions and pgvector HNSW cosine search.
   Startup rejects provider/model/dimension values that do not match the stored
   embedding metadata. Different embedding spaces are never mixed.

5. Upsert documents, aliases, and chunks. Delete chunks that disappeared from
   an existing document; revoke active documents missing from a complete,
   authoritative source snapshot. Record every ingestion run, including a
   safe provider-error stop part way through.

6. Increment the tenant corpus revision only after a consistent run. Replicas
   include the revision in their cache key and invalidate retrieval cache when
   it changes, so stale answers cannot survive a promotion or revocation.

For an emergency withdrawal:

~~~powershell
cd services/recommendation-engine
python scripts/revoke_rag_document.py <canonical_product_id> --tenant <tenant_id>
~~~

The operation makes the document inactive and increments corpus revision.
Retrieval and alias queries require active documents. The operator then verifies
zero results through protected search and purges shared cache if one is enabled.
Keep the audit record; physical deletion follows retention policy and is not
required before retrieval is blocked.

## Retrieval, answer, and security controls

- Pure live-data questions never search static RAG; they are deferred to the
  commerce system.
- A product-page product ID is a hard scope. Otherwise, exact and normalized
  aliases are tried before vector search. Equal-strength aliases remain
  ambiguous rather than silently selecting a product.
- Search filters by product, tenant, chunk type, trust level, customer-factual
  eligibility, and active document. A bounded candidate pool is rejected below
  RAG_MIN_GROUNDING_SIMILARITY.
- Claim safety is applied in SQL and again in application code. Customer output
  cannot contain mock, legacy, internal, or otherwise ineligible facts.
- The evidence selector rechecks tenancy, rejects prompt-like chunks, groups
  facts by claim key, lets a higher-authority source win, and withholds
  equal-authority contradictions.
- Context is capped at four chunks and RAG_MAX_CONTEXT_CHARS, 6,000 by default.
  Source IDs remain attached to every evidence item.
- The optional agent has exactly one read-only tool,
  search_verified_product_knowledge. It cannot browse, write data, access
  orders/payments, or call arbitrary URLs; it may make at most two tool calls.
- Every factual sentence must cite a returned chunk ID. YAFA validates citations
  and creates factual text extractively from cited chunks. Timeouts, uncited
  output, and failed validation use deterministic evidence composition instead.

Private knowledge receives a tenant ID from a trusted gateway, not a browser
body. The internal API validates the tenant header and HMAC signature.
PostgreSQL RLS is forced on documents, chunks, and aliases; the runtime role is
non-owner and lacks BYPASSRLS. Repository queries add the tenant filter too.
Cache keys include tenant and corpus revision. Encrypt connections, use Secrets
Manager, minimise logs, and never cache user-private data in a shared key.

## Capacity, resilience, and cost

The service already has a bounded TTL/LRU retrieval cache, duplicate-request
single-flight coalescing, an embedding concurrency semaphore, timeouts, short
context/output limits, two tool-call maximum, content hashing, and a repository
circuit breaker.

At 10x traffic, use horizontally scaled stateless workers behind the load
balancer, database connection pooling, HNSW monitoring/tuning, and a Redis-
backed shared tenant-safe cache and rate limiter. Isolate ingestion workers so
bulk embedding cannot starve chat. Use a deadline and cost budget: cache hit,
then exact product fact path, bounded retrieval, deterministic composition, and
only then optional model generation. Cap top-k, context, tokens, retries,
concurrency, and per-tenant spend. When budget is exhausted, return a safe
answer or unavailable response, not unlimited retries.

For vector-store failure, serve only a still-valid correctly scoped cache entry;
otherwise use the cannot-confirm/unavailable path. Use RDS Multi-AZ, backups,
restore drills, health checks, and circuit breaking. For model failure, use an
explicitly evaluated fallback Bedrock model/region only when configured and
authorised; otherwise compose from verified evidence without an LLM. Never send
sensitive context to an unapproved provider just to keep answering.

Embedding migration is blue/green: create SHADOW_VECTOR_DATABASE_URL, run
scripts/build_shadow_embedding_space.py, evaluate it, deploy a new service
revision pointed to it, canary traffic, and retain the old database for instant
rollback. Never rebuild a live embedding space in place.

## Evaluation and operational visibility

Before a corpus, prompt, embedding, reranker, or model release:

~~~powershell
cd services/recommendation-engine
python scripts/evaluate_rag.py --fixture tests/fixtures/rag_eval.json --repeats 3 --json
python scripts/evaluate_yafa_answers.py --repeats 3
pytest -q
~~~

The golden set must cover fact types, aliases/typos, product-page scope,
no-answer cases, live-data deferral, tenant isolation, revocation, conflicts,
injections, long context, and database/model outages. Gate releases on
Recall@k/MRR/nDCG, answer faithfulness and citation coverage, abstention
precision, safety, p50/p95/p99 latency, error rate, and cost. Human content and
beauty reviewers label a held-out set; LLM-as-judge is useful but not enough.

The telemetry record correlates a request ID with query hash, tenant, selected
and rejected chunk IDs/scores, conflict keys, model outcome, token counts, and
latency without logging raw customer text. Alert on empty results, top-score
distribution, retrieval diversity, citation failures, cross-tenant denials,
cache misses, Bedrock throttling, circuit-breaker opens, p95 latency, and cost.
Use canary or shadow release for risky changes and retain a rollback target.

---

## Answers to the production RAG questions

### 1. How will you build an RAG pipeline for production?

Build an auditable system: approved/versioned source -> validation/quarantine ->
semantic metadata-rich chunks -> content hashes -> dedicated vector store ->
scoped retrieval -> safety/conflict checks -> bounded cited answer -> fail-closed
fallback. Operate it with CI evaluation, traceability, IAM/RLS, backups,
budgets, staged rollout, and rollback. Keep live commerce facts in the
transaction system, not RAG.

### 2. What if RAG gives confident but wrong information?

Confidence is irrelevant without evidence. Require a citation for every factual
sentence, verify that each citation identifies a returned approved chunk, render
only grounded/extractive claims, apply a relevance threshold, and abstain when
evidence is weak. Tie user feedback to a trace ID, inspect candidates and final
context, correct/revoke the source or fix retrieval, add the case to the golden
set, and verify the fix before promotion.

### 3. What if traffic reaches 10x and latency/cost are too high?

Use shared tenant-safe caching, duplicate coalescing, connection pooling, HNSW
tuning, horizontal workers, rate limits, backpressure, and separate ingestion
workers. Reduce work in order: cache, exact product fact, bounded retrieval,
deterministic composition, LLM only if useful. Enforce token, top-k, retry,
concurrency, deadline, and per-tenant budgets. YAFA's in-process cache is an
initial control; multi-instance 10x traffic needs Redis cache/rate limiting.

### 4. What if retrieval quality suddenly drops and irrelevant documents return?

Alert on score distribution, empty results, golden-query Recall@k probes,
feedback, and embedding-space health. Contain impact by enforcing the score
floor, disabling a suspect reranker/model/corpus flag, and abstaining. Compare
the traces with the known-good release: normalization, filters, source
revision, embedding metadata, index health, candidates, and scores. Roll back
corpus/model/index/cache namespace, repair the cause, and canary the fix.

### 5. What if the same query produces a different answer every time?

Pin source revision and use stable tie-breaking, deterministic retrieval,
temperature zero, bounded tool calls, and extractive rendering. Include tenant,
corpus revision, scope, query, and policy in cache keys. Repeat golden queries
in CI. Different chunks indicate retrieval/index/cache drift; matching chunks
with different prose indicate generation nondeterminism. Use deterministic
composition while the model or prompt is investigated.

### 6. How will continuously changing documents remain up to date?

Run approved change events or complete snapshots through idempotent ingestion.
Stable IDs and hashes re-embed only changed chunks. Upserts update documents,
aliases, and chunks; reconciliation removes missing chunks and revokes documents
missing from a full snapshot. Record the run and bump corpus revision only after
completion. Failed jobs are resumable and must not mark partial knowledge as
current.

### 7. How will deleted or revoked documents stop being retrieved?

Make revocation immediate: set is_active false, stamp revoked_at, increment
tenant corpus revision, invalidate shared cache, and require active documents in
all document/chunk/alias queries. Provide an emergency revocation operation and
verify it with end-to-end search. Complete snapshots also revoke missing
documents. Do not wait for physical deletion to protect users.

### 8. How will you prevent leakage across tenants?

Derive tenant identity from authenticated server-side identity, not a browser
payload. Verify the gateway HMAC, filter every query by tenant, force PostgreSQL
RLS, use a role without BYPASSRLS, and include tenant plus authorisation scope
in cache keys. Encrypt data, minimise logs, test cross-tenant access and cache
poisoning, and use separate stores/namespaces for stronger isolation tiers.

### 9. How will you stop prompt injection in retrieved documents?

Treat documents as hostile data. Scan/quarantine instruction-like text at
ingestion and reject it again at retrieval. State that retrieved text cannot
change policy, use a typed bounded tool result, remove arbitrary tools/writes,
and validate cited output. Test direct and indirect injection, Unicode
obfuscation, prompt leaks, tool instructions, and malicious markup. Detection
helps, but tool minimisation and answer validation limit blast radius.

### 10. What if relevant chunks exceed the context window?

Retrieve a bounded pool, then use metadata filters, reranking/diversity,
deduplication by claim/source, and a strict token budget. Preserve complete
source chunks and IDs; YAFA sends at most four chunks and 6,000 characters.
Decompose complex questions into a small number of factual sub-questions or ask
for clarification. Never silently truncate a large context then claim a full
answer.

### 11. How will you handle conflicting documents?

Give conflict-prone facts a canonical claim key, source version/date, owner, and
trust level. Group retrieved evidence by claim. A higher approved authority wins
and is logged. Equal-authority contradictions are withheld, produce a
cannot-confirm answer, alert the content owner, and await correction. The LLM
never votes or chooses the more fluent claim.

### 12. How will you change embedding models without downtime?

Create a shadow database/collection using the candidate model/dimension,
re-ingest approved sources, and evaluate it against the current space and a
shadow-production sample. Deploy a revision pointed to the shadow store, canary
traffic, and retain the prior store/revision for rollback. Never mix or
overwrite live vectors. YAFA supplies the shadow-build script for this flow.

### 13. What if offline RAG is good but production RAG is poor?

Assume the test set or environment is incomplete. Compare production query mix,
language/typos, intent, permissions, freshness, filters, provider version,
timeouts, cache behaviour, and traffic patterns. Human-label privacy-safe
production failures, add them to a held-out production-like set, and distinguish
distribution shift from regression. Use online groundedness, abstention,
feedback, latency, and error metrics to expand or roll back a canary.

### 14. What if the vector database goes down?

Use health checks, short timeouts, bounded retries, circuit breaking, RDS
Multi-AZ/backups, and restore drills. Serve only a valid correctly scoped cache
entry; otherwise return safe unavailable/cannot-confirm. Do not use broad
keyword guessing as an outage replacement. Alert, fail over or restore, verify
corpus/embedding health, and close the breaker gradually.

### 15. What if the primary LLM provider goes down?

Decouple retrieval from generation. Try a pre-approved secondary model/region
only when it has least-privilege permission and passed the same safety, quality,
latency, and cost tests. If it fails, use deterministic extractive composition
from verified chunks; if there are no chunks, abstain. Never silently route
sensitive context to an unapproved provider. Maintain provider circuit breakers,
allowlists, feature flags, and outage drills.

### 16. How will you control and optimise cost?

Measure cost per successful grounded answer by tenant, intent, cache state,
model, tokens, embedding calls, vector queries, and retries. Hash and batch
ingestion; avoid unchanged embeddings; cache and coalesce safe queries; use
exact aliases; minimise context; and cap tokens, tools, retries, and
concurrency. Use deterministic composition for simple facts and an LLM only
where it adds measurable value. Use AWS Budgets, anomaly alerts, quotas, and
periodic index/content cleanup.

### 17. How will you tell retrieval failures from generation/reasoning failures?

Store a correlated trace: request ID, query hash, tenant/policy, corpus
revision, alias resolution, filters, candidate and selected chunks/scores, final
context, model/version, citations, latency, and reviewer label. Replay against
the pinned corpus. Missing, stale, incorrectly filtered, or poorly ranked
evidence is retrieval failure. Correct evidence in context but contradictory,
omitted, or overstated output is generation failure. Record both when both
happen.

### 18. How will you evaluate before production?

Use a versioned, human-reviewed golden dataset separate from tuning data. Cover
normal facts, abstentions, aliases/typos, PDP scope, live-data questions, tenant
isolation, revocation, conflicts, injection, multilingual and long-context
queries, and vector/LLM failures. Measure retrieval (Recall@k, MRR, nDCG,
filter correctness), answers (faithfulness, citation coverage, completeness,
helpfulness, safe abstention), operations (latency, availability, cache, cost),
and resilience. Repeat requests, require human review, compare candidates to
the current service, then canary/shadow deploy with explicit rollback thresholds.

## Production acceptance checklist

- [ ] Sources are approved, versioned, validated, and clear of unresolved
      quarantine/security findings.
- [ ] The dedicated vector database is private, encrypted, backed up, indexed,
      and matches the configured embedding provider/model/dimension.
- [ ] Tenant signature, RLS, cache isolation, revocation, and injection tests
      pass using the non-owner runtime database role.
- [ ] Retrieval, answer, outage, and security suites meet agreed quality and
      p95 latency thresholds.
- [ ] Dashboards, budget alarms, rollback, revocation, database restore, and
      provider-outage runbooks have owners and have been exercised.
- [ ] Canary deployment retains a tested previous corpus, service revision, and
      embedding space for immediate rollback.

