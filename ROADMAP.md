# YAFA VANAM Platform Roadmap — Phases 1–3

Status date: 2026-08-23. This document sequences the remaining work across the three
phase specs. It is a plan, not a change log; update it as milestones close.

---

## 0. Verified current state

### Phase 1 — Product Knowledge RAG

| Area | Status |
|---|---|
| Embedding provider abstraction (`app/rag/providers/`) | ✅ built, tested |
| OpenRouter Nemotron client (passage/query modes, retries, secret hygiene) | ✅ built; **live-verified**: both modes return exactly 2048 dims |
| Trust/claim policy, semantic chunker, idempotent+resumable ingestion | ✅ built, tested |
| Repository migrations (001 base, 002 VECTOR(2048)) with checksum tracking | ✅ written |
| `/internal/rag/search` + `/internal/rag/health`, token-protected | ✅ built, tested |
| Test suite | ✅ 163 passed, 7 skipped (skips = opt-in live-pgvector integration tests) |
| FastAPI → Supabase connectivity | ✅ **live-verified** (SELECT 1 OK) |
| pgvector extension on Supabase | ✅ **live-verified** |
| Migrations applied to Supabase | ✅ applied 2026-08-23, checksum-tracked (001 + 002); column verified VECTOR(2048) |
| Soft Ember single-product ingestion | ✅ 10 chunks embedded; retrieval test returns scent_profile/FAQ/benefits, zero cross-product hits |
| Full catalogue ingestion | ✅ 78 documents, 797/797 chunks embedded in one run |
| Idempotency (live proof) | ✅ re-run generated 0 embeddings, skipped all 797 unchanged, no duplicates |

**Phase 1 is CLOSED.** All success-criteria checkboxes pass. Embedding-space metadata
row recorded on Supabase: openrouter / nvidia/nemotron-3-embed-1b:free / 2048.

Known minor gaps (non-blocking):
- Migration 001 creates only the `canonical_product_id` index; spec §17 also suggests
  indexes on chunk_type/trust_level/customer_factual_eligible/metadata. Add a 003
  migration once retrieval volume justifies it — correctness first, per spec.
- The five category datasets exist in two places (repo-root `data/processed/` and
  `services/recommendation-engine/data/`). ~~Consolidate or document the source of
  truth before adapters ship.~~ ✅ resolved 2026-08-23: service copies are authoritative;
  verified byte-identical to root except eyes' filename; documented in the adapters.

### Legacy stack (to be replaced by Phase 2 architecture)

- `app/v1.py`: deterministic recommender over all five datasets. Useful logic
  (CIEDE2000, hard exclusions, routine builder, fragrance matching, kit builder),
  but violates Phase 2 rules: shared ad-hoc weights instead of per-category source
  weights, shade+formula blended into one fuzzy score, prose reason strings,
  category `if domain == ...` branches in one scorer. **Port its logic, then retire it.**
- `app/advisor/` + `app/engine/`: quiz/session advisor against Product.json;
  `engine/` is vestigial shims. Superseded.
- `app/vision/analyzer.py`: working selfie CV (quality gates, CIEDE2000, top-3 shades,
  no raw image persisted). Foundation for Phase 3 Part A.

### Infrastructure

FastAPI recommendation-engine on Railway · commerce Postgres (`DATABASE_URL`) ·
Supabase pgvector (`VECTOR_DATABASE_URL`) · Redis · Go API · Next.js storefront.
Secrets live in `.env` (gitignored) and Railway variables only.

---

## 1. Target architecture and division of authority

```text
Next.js ── Go API ── FastAPI recommendation-engine
                        │            │            │
                        │       Yafa orchestrator │
                        │         │      │      │  │
                        │   Recommendation  RAG   Whisper/CV
                        │      Engine (WHAT)  (facts)
                        │
              commerce DB + price/stock/auth (Go only)
```

Non-negotiables carried through every phase:

1. Recommendation Engine decides WHAT; RAG provides FACTS; LLM only explains.
2. Vector similarity is never the recommendation score.
3. Hard exclusions reject; colour-theory fields are ranking signals, not gates.
4. The LLM never invents product IDs — every ID validated against catalogue.
5. One Yafa; page context and conversation context are separate.
6. Go is authoritative for auth, stock, price, cart, orders, payments.
7. Raw selfies/audio are never persisted; derived attributes only.
8. Secrets never reach the browser or logs.

---

## 2. Phase 2 — Recommendation Engine + Centralized Yafa

### M1 — Canonical foundation (~first PR) — ✅ DONE 2026-08-23 (commit `f79f348`)

Shipped: `canonical/{enums,normalization,schemas}.py`, `colorimetry.py` (CIEDE2000
verbatim port), `weights.py`, `reason_codes.py`, five dataset adapters + lru_cached
registry asserting the 78-product invariant, candidate_filter (hard exclusions
reject unconditionally; soft penalties warn). Exit criteria met: all five datasets
load through adapters into canonical models; normalization unit-tested. Dataset
weight tables preferred over code defaults with drift warnings (closes the
"configurable weights" requirement at the M2 layer).

### M2 — Category engines (the scoring rewrite) — ✅ DONE 2026-08-23 (commit `d497d92`)

Create `app/recommendation/engines/{complexion,lips,cheeks,eyes,skincare,fragrance}.py`
plus `candidate_filter.py`, `scorer.py`, `ranker.py`, `reason_codes.py`.

- `enums.py` — depth, undertone, skin type, occasion, daypart, look style,
  intensity, finish, coverage, colour family, trust levels.
- `normalization.py` — hyphen/underscore/case canonicalization
  (`light-medium → light_medium`, `soft-glam → soft_glam`, `date-night → date_night`);
  original value retained for provenance.
- `schemas.py` — canonical user profile (§4 shape: complexion/skin/eyes/event/
  look/outfit/preferences, all optional) and candidate output model (§5:
  product_id, variant_id, category, score, reason_codes[], warnings[],
  source.file).
- `adapters/{skin,lips,cheeks,eyes,no_shades}.py` — one adapter per dataset file;
  each emits normalized candidates + structured profiles. Dataset loading moves
  behind adapters (port `sources()` validation).

Exit criteria: all five datasets load through adapters into canonical models;
enum normalization unit-tested; zero raw-string comparisons outside normalization.

### M2 — Category engines (the scoring rewrite)

Create `app/recommendation/engines/{complexion,lips,cheeks,eyes,skincare,fragrance}.py`
plus `candidate_filter.py`, `scorer.py`, `ranker.py`, `reason_codes.py`.

Port v1 logic per engine, fixing each violation:

- Per-category configurable weight tables (lip 1.0/.9/.7/.65/.6/.45/.4; cheek
  1.0/.9/.75/.65/.6/.45/.4; eye 1.0/.95/.8/.75/.7/.55/.4/.3) — in one config
  module, never buried in functions.
- Complexion: colour/shade stage fully separate from formula stage (§17/§18 order);
  delete the 0.7/0.3 blend.
- Skincare: use the dataset's own `scoring_model` (+2/+1/+0.5/−0.5/−1/−2/reject);
  primary-vs-secondary concern distinction; goal match, routine step, experience level.
- Compatibility rules (positive_pairing deltas) honoured with
  evidence_scope/requires_formula_confirmation preserved.
- Cheek intensity four-tier guidance; depth never eliminates shades.
- Brow: hair depth/temperature/intensity primary; Black Brown ordering (Test C).
- Mascara natural/bold gating; eyeliner neutral defaults; palette pan roles.
- Canonical machine-readable reason codes throughout (§33 vocabulary).

Exit criteria: spec §40 Tests A–E pass; golden-set regression fixture
(profiles → expected orderings) runs in CI; v1 endpoints still work via a shim.

Status: exit criteria met. Tests A–E + weights/colorimetry parity suites +
10-case golden fixture (structure pinned, never scores; double-run byte-identical)
all green — full suite 241 passed / 7 skipped, 163 pre-existing untouched.
No shim needed yet: nothing wires the engines into endpoints, so `/v1` is
untouched and still passing its own tests. Deliberate divergences from v1
(structured `color_family` fields instead of name-substring guessing; ranker
diversity with backfill) are flagged in code for the parity milestone.

### M3 — Coordination layer

Second-stage pass over per-engine winners: cheek→lip family boosting via
`recommended_lip_color_families`; cross-category cohesion boost; boldness-duplication
damping unless requested. Kit builder migrates onto coordinated output.

Exit criteria: emerald/gold soft-glam full look returns cohesive families across
eyes/cheek/lips; no triple-bold combination unless requested; coordination reasons
appear as codes.

### M4 — Yafa orchestrator core (deterministic first)

Create `app/yafa/`: `intents.py` (§28 taxonomy), `context.py` (page_context vs
conversation_context, persists across navigation), `conversation.py` (store:
in-memory first, interface ready for Postgres), `schemas.py`, `tool_router.py`,
`orchestrator.py`.

`POST /internal/yafa/chat` — token-protected. Routing:
product_information → RAG; recommendations → engines; live-data questions →
`requires_live_data` hand-off to Go. Missing-info dialogue asks only what changes
ranking (§37). Every returned ID validated against catalogue (§34). No LLM yet.

Exit criteria: typed chat works end-to-end deterministically; page-context
resolution ("what about this one?" across navigation) tested; conversation survives
navigation; intents route correctly; no LLM connected.

### M5 — LLM explanation layer

LLM provider abstraction (OpenRouter chat completions; reuse embedding-client
patterns: timeouts, bounded retries, no secrets in logs). `prompts.py` with strict
grounding: answer only from RAG chunks + engine output; reason codes rendered as
plain-language "why"; claim-safety policy reused so unverified data stays
qualified. Structured response schema (§36). Confidence UX wording (§38):
Strong/Good/Alternative bands, never raw percentages.

Exit criteria: answers cite retrieved chunks; injected/fake product IDs are refused;
claim-safety eval passes; Phase 2 success criteria (§41) green.

---

## 3. Phase 3 — Multimodal Yafa

### M6 — Selfie CV alignment (mostly hardening existing code)

Existing analyzer already covers capture guidance, face detection, quality gates,
ROI sampling, median Lab aggregation, CIEDE2000, no-persist privacy. Add/align:

- ΔE00 bands (≤1.5 exact / ≤3.2 blendable / ≤5.0 boundary / >5 mismatch) surfaced.
- Confidence anchors (0→100 … 6.0→0) with linear interpolation;
  overall = min(match_score, capture_confidence); high/medium/low UX bands.
- Neighbour graph from the shade system (`seasonal_lighter/deeper_same_undertone`,
  `horizontal_same_depth`, fallback rank-by-ΔE00) replacing bucket neighbours.
- All thresholds moved to configuration (§10); low-confidence forces retake/manual.
- Confirmation flow stores prediction AND override separately (§16).
- Formula selection after confirmation goes through the Phase 2 complexion engine,
  never RAG (§17).

Exit criteria: spec §46 shade-match test + §47 privacy tests pass; provisional
thresholds documented as needing device validation (§45).

### M7 — Outfit vision (attributes only)

Decide approach first (open decision below). Output is strictly structured:
primary_colour, secondary_colours, colour_families, style, pattern, confidence.
No product selection, no identity inference (§20). Attributes feed engines via
Yafa. `POST /internal/yafa/vision/outfit`.

Exit criteria: emerald/gold upload yields those families; outfit vision can never
emit a product ID (architecturally enforced, not prompt-enforced).

### M8 — Voice (Faster-Whisper)

Add `faster-whisper` inside the existing service (no new service prematurely).
`POST /internal/yafa/speech/transcribe` (multipart → text/language/duration).
Config: `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`. Discard audio
after transcription (§27). Transcript flows into the same `/internal/yafa/chat`
(§25) — no Voice Yafa. Benchmark CPU/RAM/latency/cold-start on Railway (§28);
split into its own service only if contention is real. Leave an unimplemented
interface for future `/speech/synthesize` (Kokoro explicitly out of scope, §50).

Exit criteria: §48 transcription eval incl. brand terms (YAFA VANAM, Soft Ember,
Miststone, Petal Velvet, Indian English samples); privacy test shows no audio retention.

### M9 — One Yafa frontend

`components/yafa/` per §29 (Provider, Drawer, Chat, Message, Input, Microphone,
ImageUpload, ProductGuidance, SuggestedQuestions, RecommendationCard, ShadeResult,
AdvisorFlow). Single conversation context across the whole site; PDP Ask-YAFA sends
page context automatically; drawer persistent everywhere; nothing resets on
navigation (§32). Recommendation cards render image/name/shade/price-from-Go/reason
codes/View/Add-to-Bag (§37, §39–40). Frontend talks to Go; Go proxies FastAPI (§41).
No secrets in `NEXT_PUBLIC_*` (§42).

### M10 — End-to-end, observability, analytics

Structured logging per §43 (conversation_id, intent, tool, latencies, fallback
reasons — never raw media). Analytics events per §44. The §49 wedding scenario as
an automated end-to-end test across every boundary. This milestone closes Phase 3.

---

## 4. Sequencing and dependencies

```text
Phase 1 closure (migrations + Soft Ember + full ingestion)
        ↓
M1 canonical/adapters ──► M2 engines ──► M3 coordination
        │                                     │
        └──────────► M4 orchestrator ──► M5 LLM layer
                          │                    │
             M6 CV align ─┤                    │
             M7 outfit ───┤                    │
             M8 whisper ──┘                    │
                          └────► M9 frontend ► M10 E2E
```

- M4 can start once M1 schemas exist (orchestrator wires whatever engines are done).
- M5 must wait until raw retrieval + engines are proven (specs forbid LLM-first).
- M6–M8 are independent of each other; all depend on M4 to be reachable from chat.
- M9 depends on M5 (answers) and benefits from M6–M8 being callable through Go.

## 5. Open decisions (need answers before the named milestone)

| # | Decision | Needed by |
|---|---|---|
| ~~1~~ | ~~Dataset location source-of-truth (service `data/` vs root `data/processed/`)~~ ✅ resolved 2026-08-23: service copies authoritative, byte-verified | ~~M1~~ |
| 2 | Conversation store: in-memory → which persistent home (own Postgres schema vs Redis) | M4 |
| 3 | Outfit vision: OpenCV heuristics first vs multimodal LLM (cost, latency, privacy) | M7 |
| 4 | Go proxy routes for internal FastAI calls (path convention + auth propagation) | M4/M9 |
| 5 | Whisper model size default (`base` vs `small`) given Railway container limits | M8 |

## 6. Risk register

- **Free-tier embeddings**: rate limits will interrupt full ingestion; resumability
  is built — expect multiple runs, don't force it.
- **Model pinning**: `nvidia/nemotron-3-embed-1b:free` verified live today; free
  models can vanish — keep the provider abstraction ready with a rebuild path
  (`scripts/rebuild_embeddings.py` exists for exactly this).
- **Supabase direct connection** (`db.<ref>.supabase.co:5432`) worked from this
  machine; if Railway-to-Supabase flakes, switch to the session pooler hostname.
- **Railway resources**: Whisper is the first heavy dependency; benchmark before
  and after; split service only on evidence.
- **Legacy removal**: retire `/v1` and advisor quiz only after golden-set parity —
  never delete working ranking behaviour before the replacement proves equivalent
  or better.

## 7. Immediate next actions

1. ~~Close Phase 1~~ ✅ done 2026-08-23 (migrations, Soft Ember, full 78-product
   ingestion, idempotency and retrieval all live-verified).
2. ~~Commit the current branch~~ ✅ Phase 2 committed in two steps: `f79f348` (M1),
   `d497d92` (M2). Phase 1 RAG code is still uncommitted on this branch — commit it
   before starting M3.
3. ~~Answer open decision #1 (dataset location)~~ ✅ service copies authoritative.
4. ~~Start M1~~ ✅ done; M2 done same day.
5. Start M3 (coordination layer) — the `CoordinationHints` seam already exists on
   every engine signature.
