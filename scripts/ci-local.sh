#!/usr/bin/env bash
# Run the same seven-runtime checks locally that CI is expected to run.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKIP_INSTALL=0
ONLY_VALIDATION=0
for arg in "$@"; do
  case "$arg" in
    --skip-install) SKIP_INSTALL=1 ;;
    --validation-only) ONLY_VALIDATION=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/ci-local.sh [--skip-install] [--validation-only]

Default: install test dependencies and run catalog/OSCU validation plus
Python, Go, Java, JavaScript, TypeScript, PHP and Ruby test suites.
--skip-install: use already-installed dependencies.
--validation-only: run static catalog/contract/config validation and Python
                   syntax compilation without requiring all language runtimes.
USAGE
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\n===== %s =====\n' "$1"; }
require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 127
  }
}

step "Static catalog and contract validation"
require python3
python3 scripts/validate-catalog.py
python3 scripts/validate-oscu-contract.py
python3 scripts/validate-production-config.py --help >/dev/null 2>&1 || true
python3 -m py_compile \
  scripts/validate-catalog.py \
  scripts/validate-oscu-contract.py \
  scripts/validate-production-config.py \
  scripts/summarize-junit.py \
  scripts/run-oscu-sandbox-check.py \
  server/app/*.py \
  languages/python/*.py

if [[ "$ONLY_VALIDATION" -eq 1 ]]; then
  echo "Validation-only checks completed."
  exit 0
fi

step "Python reference API and Python OSCU SDK"
require python3
if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  python3 -m pip install -r server/requirements-dev.txt
  python3 -m pip install -r languages/python/requirements.txt
fi
(
  cd server
  ruff check .
  mkdir -p reports
  PYTHONPATH=. pytest -q --junitxml=reports/python-junit.xml
  PYTHONPATH=../languages/python pytest -q ../languages/python --junitxml=reports/python-oscu-sdk-junit.xml
)

step "Go"
require go
(
  cd languages/go
  go test ./...
)

step "Java"
require java
require mvn
(
  cd languages/java
  mvn -B test
)

step "JavaScript"
require node
require npm
(
  cd languages/javascript
  if [[ "$SKIP_INSTALL" -eq 0 ]]; then npm install --no-audit --no-fund; fi
  npm test
)

step "TypeScript build and tests"
(
  cd languages/typescript
  if [[ "$SKIP_INSTALL" -eq 0 ]]; then npm install --no-audit --no-fund; fi
  npm test
)

step "PHP"
require php
require composer
(
  cd languages/php
  if [[ "$SKIP_INSTALL" -eq 0 ]]; then composer install --no-interaction --prefer-dist; fi
  composer test
  find src public tests -name '*.php' -print0 | xargs -0 -n1 php -l
)

step "Ruby"
require ruby
require bundle
(
  cd languages/ruby
  if [[ "$SKIP_INSTALL" -eq 0 ]]; then bundle install; fi
  bundle exec rspec
  ruby -c app.rb
  ruby -c oscu_client.rb
)

step "Docker Compose configuration"
if command -v docker >/dev/null 2>&1; then
  docker compose config --quiet
else
  echo "Docker is not installed; compose validation was not run." >&2
fi

echo
echo "All configured local CI checks completed successfully."
echo "This validates code and local test fixtures only; it does not prove KRA sandbox access, certification, or production approval."
