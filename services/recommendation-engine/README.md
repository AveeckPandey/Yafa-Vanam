# YAFA VANAM Recommendation Engine V1

An in-memory FastAPI service that deterministically ranks the authoritative 78-product YAFA VANAM development catalogue. It is rules-first: the API, not an LLM, selects products.

## Run

```powershell
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the interactive API. The existing `/advisor/*` and `/recommendations` endpoints remain available for the earlier storefront flow. The V1 engine is under `/v1`.

## Data and validation

`data/` contains the supplied authoritative development files: `skin.json`, `eyes.json`, `lips.json`, `cheeks.json`, and `no_shades.json`. They are loaded on first startup use, structurally validated, checked for duplicate IDs, and required to total 78 products. Inspect this with `GET /v1/catalogue/status`.

The service never turns mock verification fields, mock INCI, proposed SPF values, testing results, wear duration, or regulatory data into customer claims. Unverified or visually estimated colour can only contribute to internal development colour ranking. Sunbloom is described as YAFA VANAM's planned sunscreen option, not as a verified SPF claim.

## Architecture and scoring

The compact V1 implementation is in `app/v1.py`:

- loader/validator: source loading, shape validation, product-ID uniqueness;
- normalizer: accepts partial V1 beauty profiles and the legacy advisor vocabulary;
- deterministic ranker: catalogue metadata, hard exclusions, soft penalties, occasion, skin type, hair/brow, outfit, and product/variant scoring;
- colour module: CIEDE2000 for supplied LAB input, plus an outfit harmony map and shade-family diversity;
- category engines: complexion, eyes/brows, lips/liner, cheeks, skincare routines, fragrance/layering, and coordinated kits;
- API and contracts: profile normalization, dynamic quiz, feedback-event schema, and the requested category routes.

Each returned recommendation has a normalized `score` (0–1), named `score_breakdown`, customer-safe `matched_reasons`, penalties, and exclusion fields. Hard exclusions remove a candidate before scoring. Confidence combines available profile signals and the best category fit; a low-confidence response asks exactly one next question. `debug=true` adds rule names and data source for development only.

Future ML can reorder deterministic candidates once real consented feedback exists; it must not replace hard exclusions or catalogue constraints.

## Yafa multimodal pipeline

Yafa's new upstream modules keep responsibilities separate: `app/vision/analyzer.py` accepts a selfie only as in-memory bytes, performs image/face/lighting checks, samples cheek regions, derives LAB/ITA/depth/undertone, and returns three nearby shade candidates. It does not choose a product. The deterministic recommendation engine consumes confirmed or CV-derived profile fields only after this step.

`POST /v1/vision/analyse-skin` accepts multipart `image` and optional `user_id`. It never saves the raw image. If a configured PostgreSQL URL is unavailable, development uses an in-memory derived-profile store; production persistence is provided by `app/persistence/schema.sql` and enabled with `YAFA_DATABASE_URL`.

`POST /v1/profile/confirm-shade` is authoritative: a manually selected shade can never be overwritten by later CV analysis. Use `POST /v1/yafa/next-question` to receive the one next question Yafa should ask, reusing saved information before requesting a selfie.

## Contracts

The skin-analyser handoff is accepted in the profile as:

```json
{"skin_analyzer":{"lab":{"L":52.4,"a":13.7,"b":28.0},"capture_confidence":91}}
```

Manual `skin.shade_code` always wins over analyser output. The outfit-analyser contract is `context.outfit` with `primary_colour`, optional `secondary_colours`, `temperature`, `brightness`, `saturation`, and optional `confidence`.

Feedback is accepted contract-only at `POST /v1/feedback`: `recommendation_id`, `user_profile_hash`, `product_id`, optional `variant_id`, and action (`viewed`, `clicked`, `accepted`, `rejected`, `added_to_cart`, `purchased`, `shade_corrected`, or `not_my_style`). V1 does not train or persist a model.

See [API_EXAMPLES.md](API_EXAMPLES.md) for a sample dynamic quiz and ten request/response examples.

See [YAFA_MULTIMODAL_ARCHITECTURE.md](YAFA_MULTIMODAL_ARCHITECTURE.md) for boundaries, privacy behaviour, the PostgreSQL deployment contract, and the new endpoints.
