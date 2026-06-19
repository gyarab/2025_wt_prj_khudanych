# Frontend image: postaví Vue SPA (Vite) a servíruje ji nginxem.
#
# Tenhle nginx je zároveň VSTUPNÍ BRÁNA celé aplikace (publikuje port 80):
#   /          -> tahle Vue SPA (hlavní frontend, z buildu níže)
#   /api/      -> proxy na gunicorn (Django REST API)
#   /admin/    -> proxy na gunicorn (Django admin)
#   /playground/ -> proxy na gunicorn (API playground)
#   /static/   -> statické soubory Djanga (sdílený volume, plní je collectstatic)
#   /media/    -> média (sdílený volume)
# Reálnou konfiguraci nginxu mountuje compose z deploy/config/nginx.conf.

# 1) build Vue do statických souborů (JEF používá pnpm, lockfileVersion 9.0)
FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# Vue je hlavní frontend na rootu `/`, takže base zůstává default `/`.
RUN pnpm run build

# 2) runtime: nginx s nabuildovanou SPA
FROM nginx:1.27-alpine
# Hotová SPA; nginx.conf ji čeká v /usr/share/nginx/vue.
COPY --from=build /app/dist /usr/share/nginx/vue
EXPOSE 80
