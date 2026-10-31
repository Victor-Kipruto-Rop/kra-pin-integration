FROM php:8.3-cli-alpine
# Development-only server; production deployments should use PHP-FPM behind a hardened web server.
RUN apk add --no-cache curl-dev && docker-php-ext-install curl
WORKDIR /app
COPY . .
USER www-data
EXPOSE 8000
CMD ["php","-S","0.0.0.0:8000","-t","public"]
