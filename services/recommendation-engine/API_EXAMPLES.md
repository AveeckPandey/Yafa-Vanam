# API examples

All examples use `POST` unless noted. Responses are abbreviated to stable customer-facing fields; live responses additionally include score breakdown, penalties, exclusions, and confidence.

## Sample adaptive quiz

`GET /v1/quiz?intent=full_look` starts with “What can I help you with?” and then asks only relevant optional questions: known shade/skin type, eye colour, hair colour (for brows), and outfit colour. `GET /v1/quiz?intent=lips` does not ask skincare, hair, or outfit questions.

## 1. Health

`GET /health` → `{"service":"product-advisor","status":"ok","catalogue_products":78}`

## 2. Source status

`GET /v1/catalogue/status` → `{"status":"ok","datasets":{"skin":11,"eyes":15,"lips":8,"cheeks":6,"no_shades":38},"products":78,"unique_product_ids":78}`

## 3. Normalize a partial profile

```json
{"profile":{"skin":{"shade_code":"5O","skin_types":["combination"]}}}
```

`POST /v1/profile` → `{"profile":{"shade_code":"5O","shade_confirmed":true,"skin_types":["combination"],"outfit":{}}}`

## 4. Confirmed complexion shade

```json
{"profile":{"skin":{"shade_code":"5O","depth":"medium_tan","undertone":"olive","skin_types":["combination"]},"makeup_preferences":{"coverage":"medium","finish":"natural"}}}
```

`POST /v1/recommend/skin` → `{"recommendations":{"skin":{"primary_match":{"product":"Silkveil Serum Foundation","shade":{"code":"5O","name":"Olive Honey"}},"alternatives":[...],"concealer":{...}}}}`

## 5. Future skin-analyser handoff

```json
{"profile":{"skin_analyzer":{"lab":{"L":52.4,"a":13.7,"b":28.0},"capture_confidence":91},"skin":{"undertone":"olive"}}}
```

`POST /v1/recommend/skin` → ranked 24-shade candidates using CIEDE2000. Undertone is a compatibility/tie signal, never a pre-filter.

## 6. Emerald wedding eyes

```json
{"profile":{"face":{"eye_colour":"brown","hair_colour":"dark_brown","hair_depth":"deep"},"makeup_preferences":{"intensity":"soft_glam"},"context":{"occasion":"wedding","daypart":"evening","outfit":{"primary_colour":"emerald","secondary_colours":["gold"],"temperature":"warm"}}}}
```

`POST /v1/recommend/eyes` → `{"recommendations":{"eyes":{"eyeshadow":[...],"eyeliner":[...],"mascara":[...],"brows":[...]}}}`

## 7. Lip colour plus liner

```json
{"profile":{"skin":{"depth":"deep","undertone":"warm"},"makeup_preferences":{"preferred_lip_finish":"satin","intensity":"bridal"},"context":{"occasion":"wedding","outfit":{"primary_colour":"gold"}}}}
```

`POST /v1/recommend/lips` → `{"recommendations":{"lips":{"primary":{...},"alternatives":[...],"lip_liner":{...}}}}`

## 8. Coordinated cheeks

```json
{"profile":{"skin":{"depth":"deep","undertone":"warm"},"makeup_preferences":{"preferred_cheek_finish":"natural"},"context":{"outfit":{"primary_colour":"gold"}}}}
```

`POST /v1/recommend/cheeks` → `{"recommendations":{"cheeks":{"primary":{...},"alternatives":[...],"application_intensity":"build gradually to your preferred richness"}}}`

## 9. Safety-aware skincare

```json
{"profile":{"skin":{"skin_types":["dry"],"concerns":["uneven_texture"],"sensitivity":"high"},"safety_conditions":["pregnant_or_planning_pregnancy"]}}
```

`POST /v1/recommend/skincare` → `{"recommendations":{"skincare":{"am":[...],"pm":[...]}}}`. Catalogue hard exclusions completely remove Rootrenew Retinol Night Serum.

## 10. Daytime clean fragrance

```json
{"profile":{"fragrance_preferences":{"families":["citrus_green_aquatic"],"facets":["clean","fresh"],"mood":["refreshing"]},"context":{"daypart":"day","season":"summer"}}}
```

`POST /v1/recommend/fragrance` → `{"recommendations":{"fragrance":{"primary":{...},"alternatives":[...],"layering":[...]}}}`. Layering suggestions only use same `related_scent_line`; they make no performance claim.

## 11. Full coordinated look

```json
{"intent":"full_look","profile":{"skin":{"shade_code":"5O","depth":"medium_tan","undertone":"olive","skin_types":["combination"]},"face":{"eye_colour":"brown","hair_colour":"dark_brown"},"makeup_preferences":{"coverage":"medium","finish":"natural","intensity":"soft_glam"},"context":{"occasion":"wedding","outfit":{"primary_colour":"emerald","secondary_colours":["gold"]}}},"max_results_per_category":3}
```

`POST /v1/recommend` → all category blocks, a coordinated kit, profile summary, confidence, and either no follow-up or one high-information question.

## 12. Full kit and feedback

Use the full-look payload with `POST /v1/recommend/kit` to obtain one recommendation per kit role. Then send:

```json
{"recommendation_id":"req_123","user_profile_hash":"sha256:...","product_id":"yv-complex-001","variant_id":"yv-complex-001-5o","action":"accepted"}
```

to `POST /v1/feedback` → `{"accepted":true,"event":{...}}`.
