FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_MAP_ASSET_BASE_URL=""
ENV NEXT_PUBLIC_MAP_ASSET_BASE_URL=$NEXT_PUBLIC_MAP_ASSET_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS runner
ARG GIT_REVISION=unknown
LABEL org.opencontainers.image.revision=$GIT_REVISION
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN groupadd --system --gid 1001 ecotwin && \
    useradd --system --uid 1001 --gid 1001 ecotwin
COPY --from=builder --chown=ecotwin:ecotwin /app/.next/standalone ./
COPY --from=builder --chown=ecotwin:ecotwin /app/.next/static ./.next/static
COPY --from=builder --chown=ecotwin:ecotwin /app/public ./public
USER 1001:1001
EXPOSE 3000
CMD ["node", "server.js"]
