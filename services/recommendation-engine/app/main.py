from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.advisor import router as advisor_router
from app.advisor.catalogue import load_catalogue
from app.advisor.models import BeautyProfile
from app.advisor.recommender import recommend
from app.v1 import router as v1_router

app = FastAPI(title="YAFA VANAM Product Advisor", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(advisor_router)
app.include_router(v1_router)


@app.get("/health")
def health() -> dict[str, str | int]:
    return {"service": "product-advisor", "status": "ok", "catalogue_products": len(load_catalogue())}


@app.post("/recommendations")
def recommendations(profile: BeautyProfile) -> dict:
    # Backward-compatible stateless endpoint. Commerce fields still require Go validation.
    return {"profile": profile.model_dump(mode="json"), "recommendations": [r.model_dump(mode="json") for r in recommend(profile)]}
