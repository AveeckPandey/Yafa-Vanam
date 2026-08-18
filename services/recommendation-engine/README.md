# YAFA VANAM Product Advisor / Recommendation Engine

FastAPI V1 for deterministic, catalogue-grounded makeup recommendations.

```bash
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

Catalogue path defaults to `../../data/processed/Product.json` from the service source tree and can be overridden with `YAFA_CATALOGUE_PATH`.

See `../../docs/makeup-advisor-v1.md` for API and authority boundaries.
