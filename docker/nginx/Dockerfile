FROM nginx:1.31.4-alpine

# To locally connect your container image to a repository:
LABEL org.opencontainers.image.source=https://github.com/SojusanApps/game-list-backend

RUN apk --no-cache add curl=8.21.0-r0 \
    && mkdir /etc/nginx/ssl \
    && rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d
COPY proxy.conf /etc/nginx
