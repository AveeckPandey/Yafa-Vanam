FROM node:22-alpine AS build
WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/frontend-types/package.json ./packages/frontend-types/package.json
RUN npm ci

COPY apps/web ./apps/web
COPY packages/frontend-types ./packages/frontend-types
COPY data/processed ./data/processed
COPY services/recommendation-engine/data ./services/recommendation-engine/data
WORKDIR /workspace/apps/web
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

RUN addgroup -S yafa && adduser -S yafa -G yafa
COPY --from=build --chown=yafa:yafa /workspace/apps/web/.next/standalone ./
# The standalone bundle retains the monorepo path (`apps/web`).  Keep the
# static assets and public files alongside that generated server.
COPY --from=build --chown=yafa:yafa /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=yafa:yafa /workspace/apps/web/public ./apps/web/public

USER yafa
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
