# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production stage
FROM caddy:2-alpine

# Replace default nginx config
COPY Caddyfile /etc/caddy/Caddyfile
# Copy built frontend
COPY --from=build /app/dist /usr/share/caddy

EXPOSE 80
