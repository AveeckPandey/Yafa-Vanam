# Yafa multimodal architecture

## Boundaries

```text
Selfie/outfit analysis -> derived attributes -> deterministic recommendation engine -> structured result
                                                      |                         |
                                                    RAG                    Yafa/LLM
                                                verified facts only      conversation/explanation only
```

Vision, RAG, and Yafa never select products. The recommendation service remains the sole deterministic product and variant selector.

## Privacy-safe selfie flow

`POST /v1/vision/analyse-skin` receives multipart image bytes, processes them in memory, and returns either a retake result or derived LAB, ITA, depth family, undertone, confidence, and three shade candidates. It checks image size, brightness, overexposure, blur, colour cast, and zero/multiple detected faces. The raw image is never written to disk, returned, or passed to profile persistence.

On success the optional `user_id` writes only derived data. The development store is in-memory. Set `YAFA_DATABASE_URL` in production after applying `app/persistence/schema.sql` to use PostgreSQL. The schema intentionally has no photo/image/blob column.

## Profile precedence

1. Manual confirmed shade
2. Existing confirmed profile
3. Current computer-vision estimate
4. Quiz-only estimate

`POST /v1/profile/confirm-shade` validates the supplied code against the YAFA 24-shade system and persists it as manual/confirmed. New CV events leave that confirmation intact.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/vision/analyse-skin` | Temporary selfie analysis; multipart `image`, optional `user_id` |
| `GET /v1/profile/beauty?user_id=` | Read derived profile only |
| `PATCH /v1/profile/beauty` | Save partial derived/user preference fields |
| `POST /v1/profile/confirm-shade` | Persist an authoritative manual shade correction |
| `POST /v1/yafa/next-question` | Return the single next adaptive Yafa question |
| `POST /v1/recommend*` | Deterministic category, look, and kit recommendations |

## Example CV response

```json
{
  "quality_pass": true,
  "face_detected": true,
  "analysis": {"lab": {"L": 52.4, "a": 13.7, "b": 28.0}, "ita": 4.8, "depth_family": "medium_tan", "undertone": "olive"},
  "shade_candidates": [
    {"shade_code": "5O", "shade_name": "Olive Honey", "role": "best_match", "colour_distance": 0.2, "confidence": 0.95},
    {"shade_code": "4O", "shade_name": "Olive Almond", "role": "slightly_lighter", "colour_distance": 4.1, "confidence": 0.84},
    {"shade_code": "6N", "shade_name": "Caramel Earth", "role": "slightly_deeper", "colour_distance": 4.5, "confidence": 0.82}
  ],
  "confidence": 0.89,
  "raw_image_persisted": false
}
```

The values above illustrate the contract. A real response is calculated from the uploaded image and is not manufacturer-validated colour measurement.
