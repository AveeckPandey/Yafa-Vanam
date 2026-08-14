# Recommendation gateway

The Go API is the commerce gateway to the Python/FastAPI recommendation engine. The Python service returns ranked product IDs/scores; Go enriches the result with current price, inventory, active status, region restrictions, and other business truth before the recommendation reaches the storefront.
