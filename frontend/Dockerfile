FROM node:22-alpine AS base
WORKDIR /app

FROM base AS dev
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
EXPOSE 19104
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "19104", "--strictPort"]

FROM base AS build
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM nginx:stable-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
