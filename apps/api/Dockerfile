FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/yafa-api ./cmd/api

FROM alpine:3.21
WORKDIR /app
COPY --from=build /out/yafa-api /app/yafa-api
EXPOSE 4000
CMD ["/app/yafa-api"]
