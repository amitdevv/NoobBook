# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty VITE_API_HOST makes the frontend use same-origin requests,
# which nginx will proxy to the backend container.
ENV VITE_API_HOST=""
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Container-readiness probe. Without this, Docker reports the
# container as "Up" the instant the nginx process spawns — but
# before nginx has actually bound to :80. Coolify / Traefik then
# routes traffic at the not-yet-listening container during a fresh
# build, producing the 504 Gateway Timeout window we kept hitting.
# A HEALTHCHECK lets the orchestrator wait for `healthy` before
# switching upstream traffic over.
#
# `wget` is part of the busybox bundled with nginx:alpine, so no
# extra package install. start-period=3s gives nginx time to bind
# before the first probe; interval=10s + retries=2 reacts inside
# ~30s if it ever crashes after start.
HEALTHCHECK --interval=10s --timeout=3s --start-period=3s --retries=2 \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
