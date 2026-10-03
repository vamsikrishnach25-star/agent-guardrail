# Multi-stage: build the static bundle with Node, then serve it with nginx.
# The built bundle is just static files - no need to ship Node or the
# dashboard's dev dependencies in the final image.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci (not install) - installs exactly what's in package-lock.json,
# failing loudly if it's out of sync with package.json, rather than
# silently resolving different versions than what's actually tested.
RUN npm ci
COPY . .
# Baked in at build time - Vite inlines env vars into the static bundle,
# there's no runtime env for a plain static file server to read from.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
