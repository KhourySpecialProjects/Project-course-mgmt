# syntax=docker/dockerfile:1
#
# Web image. Three stages:
#   dev   - used by docker-compose.yml; source is mounted in and the page
#           hot-reloads on every save.
#   build - compiles the production bundle.
#   prod  - a small image that only runs the compiled app.

FROM node:22-alpine AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# ---------------------------------------------------------------- dev
FROM base AS dev
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
EXPOSE 3000
# Uses webpack with file polling (see the "dev:docker" script and
# WATCHPACK_POLLING in docker-compose.yml): it reliably notices file changes
# made on your computer, which Turbopack's watcher can miss inside a container.
CMD ["npm", "run", "dev:docker"]

# ---------------------------------------------------------------- build
FROM base AS build
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
# The /api rewrite target is fixed at build time for production builds.
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
RUN npm run build

# ---------------------------------------------------------------- prod
FROM base AS prod
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
