FROM oven/bun:1 AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile

# Build the static export
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_RAG_ENABLED=false
ENV NEXT_PUBLIC_RAG_ENABLED=$NEXT_PUBLIC_RAG_ENABLED

ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_WS_URL=""
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

ENV NEXT_TELEMETRY_DISABLED=1
RUN bun run build

# The output is in /app/out (static files)
# For S3 deployment, copy from this stage:
#   docker cp $(docker create --name tmp builder):/app/out ./out && docker rm tmp
# Or use a simple nginx to serve locally:
FROM nginx:alpine AS runner

COPY --from=builder /app/out /usr/share/nginx/html

# SPA fallback routing
RUN printf 'server {\n\
  listen 3000;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location / {\n\
    try_files $uri $uri.html $uri/ /index.html;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
