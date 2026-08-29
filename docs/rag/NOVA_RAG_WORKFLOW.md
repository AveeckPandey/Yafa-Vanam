# YAFA VANAM Nova + RAG workflow

## Purpose

The YAFA VANAM assistant combines natural conversation from Amazon Nova with verified information retrieved from the YAFA knowledge base. The design separates conversation, knowledge, recommendations, and live commerce data so the assistant can sound helpful without inventing product or company facts.

## Current production status

| Capability | Status | Notes |
| --- | --- | --- |
| Product and brand knowledge database | Live | 79 source documents and 806 embedded chunks are stored in the dedicated `yafa_rag` PostgreSQL database. |
| Semantic retrieval | Live | Both existing application instances use Amazon Titan Text Embeddings V2 with 1,024 dimensions and pgvector. |
| Greetings and conversational routing | Implemented | Greetings and general conversation do not require a product search. |
| Product and policy answers | Implemented and backed by live RAG | Answers can be grounded in the product catalogue and owner-approved brand policy. |
| Nova knowledge tool | Implemented and tested | Nova can call `consult_yafa_knowledge`; final public voice-path verification is still required. |
| Live price, stock, cart, payment, and order tools | Separate concern | These must use the commerce system, not RAG. |

## Runtime conversation workflow

```text
Customer text or voice
        |
        v
Amazon Nova voice/conversation session
        |
        v
Intent and safety decision
   |          |              |
   |          |              +--> Live commerce question
   |          |                   Use commerce API; never RAG
   |          |
   |          +--> Product, ingredient, usage, warning,
   |               vegan, cruelty-free, charity, or policy question
   |               Call consult_yafa_knowledge
   |
   +--> Greeting, small talk, or incomplete styling request
        Answer naturally or ask one useful question
                       |
                       v
          Recommendation service /internal/yafa/chat
                       |
                       v
          pgvector retrieves relevant verified chunks
                       |
                       v
          Guardrails validate intent, grounding, and boundaries
                       |
                       v
          Nova turns the verified result into a short human response
                       |
                       v
                    Customer
```

### 1. Receive the customer request

Nova receives speech or text and keeps the response conversational. Voice answers should normally be one to three sentences and ask no more than one useful follow-up question at a time.

### 2. Decide which information source is appropriate

The assistant classifies the request by responsibility:

- Greetings and small talk: respond directly. Never return “no product found.”
- Outfit and makeup guidance: use the outfit colour, occasion, desired intensity, skin depth, and undertone. Ask for the most important missing detail.
- YAFA product or company facts: call the knowledge tool before answering.
- Current price, stock, discount, delivery, cart, payment, refund, or order status: use the live commerce API. RAG is not authoritative for changing transactional data.
- Medical or reaction questions: provide general safety guidance, recommend patch testing where appropriate, and escalate serious or persistent symptoms to a qualified clinician.

### 3. Retrieve verified knowledge

For a factual YAFA question, Nova calls `consult_yafa_knowledge` with the customer’s complete question. A product ID is supplied only when it already comes from trusted page or session context.

The tool sends the request to the protected recommendation endpoint. The recommendation service embeds the query with Amazon Titan Text Embeddings V2 and searches the `yafa_rag` pgvector database. It returns a customer-ready answer, its intent, and up to four grounding records.

### 4. Apply answer boundaries

Nova uses the retrieved answer but does not reveal internal chunks, similarity scores, service names, tokens, or errors. It must not invent product names, shades, ingredients, certifications, vegan status, or charitable recipients.

If retrieval is temporarily unavailable, the assistant says it cannot verify that detail right now and continues helping with preferences. It does not replace missing facts with guesses.

### 5. Respond naturally

Nova converts the grounded result into YAFA’s voice: warm, concise, confident, and helpful rather than overly promotional. The assistant should answer first, then ask one relevant follow-up question only when it advances the customer’s goal.

## Knowledge ingestion workflow

```text
Product.json + BrandKnowledge.json + approved policy documents
                              |
                              v
                  Validate structure and required fields
                              |
                              v
             Split content into searchable knowledge chunks
                              |
                              v
       Generate 1,024-dimensional Titan V2 embeddings
                              |
                              v
          Upsert documents, chunks, metadata, and vectors
                              |
                              v
     Run health, dimension, retrieval, and policy-answer checks
                              |
                              v
                      Promote the release
```

The catalogue currently contributes 78 product documents. `BrandKnowledge.json` contributes the conversational guidance and approved cruelty-free, vegan, giving, safety, and fallback information. Together they produce 79 documents and 806 searchable chunks.

Re-ingestion should be idempotent: unchanged records are updated safely, obsolete chunks are removed, and the stored embedding model and dimension are checked before the service is marked healthy.

## Responsibility boundaries

| Domain | Authoritative source | Examples |
| --- | --- | --- |
| Product knowledge | RAG knowledge base | Ingredients, benefits, usage, warnings, product descriptions |
| Brand policy | Approved brand knowledge and policy document | Cruelty-Free*, Vegan*, Giving* |
| Recommendations | Recommendation rules and ranking logic | Suitable products, look construction, shade candidates |
| Live commerce | Commerce database/API | Price, stock, discounts, cart, checkout, orders, refunds |
| Conversation | Amazon Nova system prompt | Tone, clarification, short spoken responses |
| Safety | Deterministic guardrails plus approved wording | Patch testing, adverse-reaction escalation, no medical diagnosis |

## Deployment workflow

1. Validate the JSON sources and run unit/integration tests.
2. Build an immutable recommendation-service container image.
3. Publish the image to the private ECR repository with a unique release tag.
4. Deploy to one EC2 instance as a canary.
5. Verify base health, RAG database connectivity, pgvector, embedding dimensions, and representative queries.
6. Deploy the same immutable image to the second instance with automatic rollback.
7. Verify both instances are healthy and in service.
8. Move the `production` image tag to the verified image.
9. Create a new launch-template version containing the same RAG environment settings and make the Auto Scaling group use it for future replacements.
10. Verify the public storefront and Nova voice path without exposing internal endpoints or secrets.

No new database instance is required for this workflow. The isolated `yafa_rag` logical database uses the existing private PostgreSQL server, while keeping vector tables separate from the commerce database.

## Improvements over time

### Immediate: production completion and reliability

- Complete the public Nova voice-path test: greeting, product fact, outfit guidance, skin-tone guidance, policy question, unavailable-service fallback, and safety escalation.
- Persist the release in the ECR `production` tag and Auto Scaling launch template so replacement instances cannot revert to the old configuration.
- Add a single authenticated smoke-test command that verifies the correct `/internal/rag/health` route and a small set of representative questions.
- Add CloudWatch alarms for unhealthy targets, RAG database failures, Bedrock errors, high latency, and repeated fallback responses.
- Replace Docker’s stored login credential with the Amazon ECR credential helper to remove the current local credential warning.

### Near term: answer quality

- Add structured shade data: skin depth, undertone, finish, coverage, shade family, and verified swatch references.
- Add structured outfit guidance for colour family, contrast, occasion, time of day, and desired intensity.
- Introduce a deterministic recommendation stage after retrieval. Semantic similarity should find facts, not decide the final product ranking by itself.
- Add spelling, synonym, and multilingual support for common customer phrasing.
- Create a reviewed test set from real customer questions and measure grounded-answer accuracy, retrieval recall, citation correctness, and fallback quality.
- Record anonymous failure categories such as “no useful chunk,” “wrong intent,” and “missing live-data tool” without storing unnecessary personal or voice data.

### Medium term: governance and freshness

- Give every knowledge record an owner, approval state, effective date, review date, and source version.
- Require policy approval before changing cruelty-free, vegan, certification, or charitable-giving claims.
- Add product-level Vegan* evidence instead of inferring the claim from botanical branding.
- Publish the annual Giving* recipients and allocation only after they are formally selected and verified.
- Run incremental ingestion when a product or policy changes instead of rebuilding all embeddings.
- Keep an audit trail that connects each deployed answer source to its approved document version.

### Longer term: personalization and multimodal assistance

- Use customer-provided outfit photos to extract colour palettes, while clearly asking consent and applying retention limits.
- Add calibrated complexion and undertone assistance that presents suggestions rather than claiming perfect shade matching from a camera.
- Combine customer preferences, allergies they voluntarily provide, prior purchases, and occasion context with explicit consent and deletion controls.
- Add human handoff for sensitive reactions, unresolved orders, and questions requiring company confirmation.
- Evaluate multilingual Nova responses while keeping retrieved product and policy facts consistent across languages.

## Cost-aware operation

The current design reuses the existing two application instances and existing PostgreSQL server. Improvements should first focus on observability, incremental ingestion, caching repeated safe queries, and batching embeddings rather than adding infrastructure.

Free Tier or promotional-credit coverage depends on the AWS account’s eligibility, start date, region, service usage, and current AWS terms. Infrastructure health cannot prove that both always-on instances or Bedrock calls are free. Enable an AWS Budget and billing alerts, then review EC2 instance-hours, RDS hours/storage, NAT data processing, load-balancer hours, CloudWatch logs, ECR storage, and Bedrock requests regularly.

## Definition of done for each future release

A knowledge release is complete only when:

- source documents are approved and versioned;
- automated tests pass;
- stored and configured embedding dimensions match;
- representative retrieval questions return the expected sources;
- greetings do not trigger product-not-found behavior;
- live commerce questions are routed away from RAG;
- safety and unavailable-service fallbacks behave correctly;
- both production instances run the same immutable image;
- the ECR production tag and launch template point to that release;
- public storefront and Nova voice checks pass; and
- monitoring shows no regression after deployment.
