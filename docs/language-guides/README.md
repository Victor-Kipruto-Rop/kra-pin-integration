# Language guides

Standalone server templates: Go (`go test ./... && go run .`), Java (`mvn test && mvn spring-boot:run`), JavaScript (`npm test && npm start`), TypeScript (`npm install && npm test && npm start`), PHP (`composer install && composer test`, serve with PHP built-in server), Ruby (`bundle install && bundle exec rspec && bundle exec rackup`). Set KRA_MOCK=true and PROXY_API_KEYS before starting. Never commit .env files.
