FROM golang:1.23-alpine AS build
WORKDIR /src
COPY apps/api/go.mod ./apps/api/go.mod
COPY apps/api ./apps/api
COPY data/processed/Product.json ./data/processed/Product.json
WORKDIR /src/apps/api
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -o /out/yafa-api ./cmd/api

FROM alpine:3.20
RUN addgroup -S yafa && adduser -S yafa -G yafa
WORKDIR /app
COPY --from=build /out/yafa-api /app/yafa-api
COPY --from=build /src/data/processed/Product.json /app/data/processed/Product.json
COPY --from=build /src/apps/api/db/migrations /app/db/migrations
ENV YAFA_CATALOGUE_PATH=/app/data/processed/Product.json
USER yafa
EXPOSE 4000
CMD ["/app/yafa-api"]
