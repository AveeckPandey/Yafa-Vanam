# YAFA production RAG controls

The service fails closed: it only answers from active, tenant-scoped, approved
facts. If retrieval, citations, source safety, or conflict checks fail, YAFA
uses its deterministic "cannot confirm" path instead of guessing.

## Operating controls

1. Run `python scripts/evaluate_rag.py --fixture tests/fixtures/rag_eval.json --repeats 3 --json` and `python scripts/evaluate_yafa_answers.py --repeats 3` in CI before enabling a new corpus, embedding model, or agent model; fail deployment on retrieval drift, unstable answers, grounding failures, or latency regression.
2. Record real-query feedback and inspect the structured `yafa.rag.telemetry` CloudWatch logs: candidate IDs/scores, filtered IDs, conflict keys, model result, and latency share one request trace.
3. Ingest on each approved source update. Hashing makes unchanged chunks free; removed chunks are deleted. Run `scripts/revoke_rag_document.py PRODUCT_ID` for immediate withdrawal.
4. Private knowledge must have a tenant ID. The trusted internal gateway supplies `X-Yafa-Tenant-Id` plus an HMAC `X-Yafa-Tenant-Signature`; PostgreSQL forced RLS and repository filters protect documents, chunks, and aliases. The browser must never receive the tenant-signing secret.
5. Ingestion and retrieval quarantine instruction-like source content. The agent receives source data in a bounded tool result and is told that retrieved text is data, never instructions.
6. Sources must set `metadata.claim_key` for facts that can conflict. Equal-authority contradictory claims are withheld; a higher provenance claim wins. Conflicts create an alert from telemetry.
7. Context is bounded by `RAG_MAX_CONTEXT_CHARS`, four chunks, and two tool calls. The agent uses temperature zero and requires a citation per factual sentence.
8. The retrieval circuit breaker opens after repeated vector-store failures. YAFA does not fabricate an answer; provision RDS Multi-AZ/read replica and alarm on breaker openings.
9. A Bedrock model failure falls back to deterministic evidence composition by default. Set `YAFA_AGENT_FALLBACK_MODEL` only after granting its exact `bedrock:InvokeModel` permission and passing its evaluation suite.
10. Cost controls are cache TTL/namespace, request coalescing, concurrency limits, short output/context limits, and agent tool-call limits. Add AWS Budgets and CloudWatch alarms per environment.

## Embedding migrations without downtime

The legacy in-place rebuild now refuses to run when `APP_ENV=production`.
Set `SHADOW_VECTOR_DATABASE_URL` to a fresh pgvector database and run
`python scripts/build_shadow_embedding_space.py`. Evaluate that database,
deploy a new service revision pointing to it, and switch traffic through the
load balancer/ECS deployment. The old database remains the instant rollback;
the two embedding spaces are never mixed or unavailable at the same time.
