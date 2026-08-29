# RAG

The product and brand knowledge database is now implemented for the recommendation service. See [Nova + RAG workflow](./NOVA_RAG_WORKFLOW.md) for the runtime flow, ingestion process, deployment checklist, responsibility boundaries, and improvement roadmap.

RAG supports grounded product, ingredient, skincare, and customer-policy explanations. An internal Retool staff assistant remains a possible later use.

Use RAG for knowledge retrieval and explanation, not for deterministic commerce truth such as current inventory, payments, refund amount, order status, coupon eligibility, or bestseller ranking.

Initial text-RAG content: catalogue, ingredients, benefits, concerns, skin types, usage, warnings, FAQs, and policies. Product image URLs can be attached as metadata to retrieved products. Multimodal image embeddings/visual similarity can be explored later.
