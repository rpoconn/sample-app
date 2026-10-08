# Build context is the repo root: bun.lock and the bun workspaces live there.
FROM oven/bun:1 AS build

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer
COPY package.json bun.lock ./
COPY frontend/package.json frontend/
COPY packages/react-email/package.json packages/react-email/
RUN bun install --frozen-lockfile

COPY frontend frontend

# Empty means same-origin requests; nginx proxies /api to the backend
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

# vite.config.ts writes the build to backend/app/frontend
RUN bun run --filter frontend build

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/backend/app/frontend /usr/share/nginx/html
EXPOSE 80
