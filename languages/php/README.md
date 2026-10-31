# PHP service

Requires PHP 8.2+ and cURL. Run `composer install`, export variables from `.env.example`, then run the development server with `php -S 127.0.0.1:8000 -t public`. Tests: `composer test`. Demo PIN A000000000B; ID 00000000. Server-side only. Add a shared gateway rate limiter for production replicas and verify KRA response fields in sandbox.


**Production deployment:** The PHP built-in server and included CLI Dockerfile are development-only. Deploy PHP-FPM behind a hardened web server or ingress, with TLS, process supervision and centralized rate limiting.
