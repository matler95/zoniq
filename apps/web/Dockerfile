FROM node:24-bookworm-slim AS build

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm --filter @zoniq/web build

FROM node:24-bookworm-slim AS runtime

ENV NODE_ENV=production
RUN useradd --system --uid 1001 zoniq
COPY --from=build --chown=zoniq:zoniq /app/apps/web/.next/standalone /app
COPY --from=build --chown=zoniq:zoniq /app/apps/web/.next/static /app/apps/web/.next/static
USER zoniq

EXPOSE 3000

CMD ["node", "/app/apps/web/server.js"]
