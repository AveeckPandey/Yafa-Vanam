# YAFA VANAM RAG Assistant — future service

This service is planned for a later phase. It will provide grounded knowledge retrieval for the customer beauty companion and internal staff tools.

## Initial text-RAG sources

- YAFA VANAM product catalogue
- product descriptions and benefits
- ingredient information
- skin types and concerns
- usage instructions and warnings
- shade descriptions
- shipping, return, refund, privacy, and support policies
- curated FAQs

Product images remain linked as product assets so a retrieved product can be returned with its image/card. Multimodal image embeddings and visual search are a later extension, not part of V1.

## Planned request path

Next.js -> Go API -> RAG FastAPI service -> retrieval/vector store -> LLM -> Go safety/business layer -> Next.js.

The RAG service must not be the source of truth for price, stock, order status, refunds, payments, bestseller rankings, or coupon eligibility. Those remain deterministic Go/PostgreSQL responsibilities.
