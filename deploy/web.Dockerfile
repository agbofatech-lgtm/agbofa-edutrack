FROM node:22-alpine AS build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.29-alpine
RUN apk add --no-cache gettext
COPY deploy/nginx-unprivileged.conf /etc/nginx/nginx.conf
COPY deploy/nginx-web.conf.template /etc/nginx/default.conf.template
COPY deploy/web-entrypoint.sh /usr/local/bin/edutrack-web-entrypoint
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
RUN chmod 0555 /usr/local/bin/edutrack-web-entrypoint \
    && mkdir -p /tmp/nginx-conf /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /tmp/nginx-conf /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

USER nginx
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/edutrack-web-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
