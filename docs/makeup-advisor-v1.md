# YAFA VANAM Makeup Advisor V1

## What is implemented

The existing `services/recommendation-engine` is retained and extended as the Product Advisor. It now provides typed advisor sessions, adaptive quiz branching, Beauty Profile state, the 24-shade complexion matcher, deterministic product/variant ranking, supporting-complexion suitability mapping, follow-up preference modifications, vision/RAG provider interfaces, and deterministic tests.

The uploaded catalogue snapshot is stored at `data/processed/Product.json` and is the advisor's catalogue source. The service never creates product or shade names.

## Authority boundaries

- Product Advisor: filtering, compatibility, shade matching, deterministic scores, ranking and recommendation selection.
- Go commerce API: price, stock, SKU, sellability, orders, discounts, refunds and all side effects.
- Vision: optional depth/undertone estimate and outfit colour extraction; a real provider must supply confidence. No sensitive-trait inference.
- RAG: product facts and recommendation explanations. It may not override deterministic ranking or invent commerce/formula facts.

`stock: null` is therefore not interpreted as out-of-stock. Recommendation responses set `commerce_validation_required=true` so the Go layer must validate before cart/checkout.

## Advisor API

- `POST /advisor/session`
- `GET /advisor/session/{id}`
- `POST /advisor/session/{id}/answer`
- `POST /advisor/session/{id}/image-analysis`
- `POST /advisor/session/{id}/recommend`
- `POST /advisor/session/{id}/modify`
- `POST /advisor/session/{id}/explain`

The old stateless `POST /recommendations` endpoint remains for compatibility and accepts a typed `BeautyProfile`.

## Local run

```bash
cd services/recommendation-engine
python -m venv .venv
# activate it
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

At repository root:

```bash
npm install
npm run dev:web
```

Set `NEXT_PUBLIC_ADVISOR_URL=http://localhost:8000` for local UI-to-advisor calls.

## Vision

The upload endpoint and UI are complete, but V1 does not pretend to analyze an image when no provider is configured. `DisabledVisionProvider` returns `not_configured`. Implement a provider adapter behind `VisionProvider`, keep processing transient by default, return confidence, then ask the customer to confirm before updating the Beauty Profile.

Selfie guidance in the UI/spec is natural daylight, no beauty filter, minimal/no foundation, clear face, and no strongly coloured lighting.

## RAG

`RagProvider` is an explicit boundary. Until the separate RAG service is connected, `/explain` produces a deterministic explanation from the winning score reasons and product/variant IDs. This keeps explanations grounded without allowing an LLM to choose products.

## Session persistence

V1 uses a thread-safe 24-hour in-memory `InMemorySessionStore`. It is intentionally behind a store interface boundary. For multi-instance production deployment, replace it with PostgreSQL/Redis-backed session persistence before horizontal scaling.

Saved long-term Beauty Profiles are not enabled by default. Do not persist selfies by default; obtain consent before saving optional profile data.

## Commerce integration

The Go commerce service now validates exact `product_id + variant_id` pairs and owns anonymous cart writes and price totals. Recommendation cards can send these IDs through the storefront `/api/cart` adapter. Durable PostgreSQL cart persistence and direct complete-look bundle actions remain follow-up work.

## Analytics events

The web event vocabulary includes:

`advisor_opened`, `advisor_goal_selected`, `quiz_answered`, `image_analysis_requested`, `image_analysis_confirmed`, `recommendations_generated`, `recommendation_viewed`, `recommendation_changed`, `product_clicked`, `variant_selected`, `add_to_cart`, `complete_look_added`, `purchase_completed`, `product_returned`, and `shade_exchange_requested`.

Always include `session_id` on advisor/recommendation events where possible.

## Deterministic guarantees covered by tests

- Medium-Tan + Olive -> `5O Olive Honey`.
- Exact shade stays the same across the six shared-shade complexion products.
- Brightening concealer moves one validated depth lighter, not an arbitrary jump.
- Corrector is not recommended unless a discoloration concern is explicit.
- Volume/Lift/Tubing mascara differentiation remains deterministic.
- `unknown` does not create fake profile values.
- Follow-up preference changes preserve stable prior answers.
- Disabled vision never fabricates analysis.
