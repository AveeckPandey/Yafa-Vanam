FROM python:3.12-slim

WORKDIR /app/services/recommendation-engine
COPY services/recommendation-engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/recommendation-engine/app ./app
COPY data/processed/products.json /app/data/processed/products.json

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
