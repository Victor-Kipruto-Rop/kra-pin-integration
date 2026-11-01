.PHONY: help validate test test-all test-python test-go test-java test-js test-ts test-php test-ruby compose-config sandbox-dry-run

help:
	@echo "Targets: validate test test-all test-python test-go test-java test-js test-ts test-php test-ruby compose-config sandbox-dry-run"

validate:
	python3 scripts/validate-catalog.py
	python3 scripts/validate-oscu-contract.py
	python3 -m py_compile scripts/*.py server/app/*.py languages/python/*.py

test test-all:
	bash scripts/ci-local.sh

test-python:
	cd server && ruff check . && PYTHONPATH=. pytest -q && PYTHONPATH=../languages/python pytest -q ../languages/python

test-go:
	cd languages/go && go test ./...

test-java:
	cd languages/java && mvn -B test

test-js:
	cd languages/javascript && npm test

test-ts:
	cd languages/typescript && npm test

test-php:
	cd languages/php && composer test

test-ruby:
	cd languages/ruby && bundle exec rspec

compose-config:
	docker compose config --quiet
	docker compose -f docker-compose.multilang.yml config --quiet

sandbox-dry-run:
	@test -n "$(OPERATION)" || (echo "Set OPERATION=<operation-id>"; exit 2)
	@test -n "$(PAYLOAD)" || (echo "Set PAYLOAD=<path-to-json>"; exit 2)
	python3 scripts/run-oscu-sandbox-check.py --operation "$(OPERATION)" --payload "$(PAYLOAD)"
