FROM node:24.16-bullseye AS build
WORKDIR /app
COPY ./frontend /app
RUN npm ci && npm run build

FROM nginx:1.30-trixie-perl
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
