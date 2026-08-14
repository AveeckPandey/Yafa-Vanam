# Recommendation system

The recommendation engine remains a Python/FastAPI service because the ranking, data processing, and later ML work are Python-centric.

The service should return ranked product IDs/scores. The Go commerce API then checks current product status, stock, price, variant availability, and other business rules before returning recommendations to Next.js.
