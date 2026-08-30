FROM python:3.12-slim

WORKDIR /app/services/recommendation-engine
COPY services/recommendation-engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 yafa
COPY services/recommendation-engine/app ./app
COPY data/processed/Product.json /app/data/processed/Product.json
COPY data/processed/BrandKnowledge.json /app/data/processed/BrandKnowledge.json
COPY services/recommendation-engine/migrations ./migrations
COPY services/recommendation-engine/scripts ./scripts

USER yafa
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
