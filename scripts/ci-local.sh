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
Usage: bash scripts/ci-local.sh [--skip-install] [--validation-only]

Default: install test dependencies and run catalog/OSCU validation plus
Python, Go, Java, JavaScript, TypeScript, PHP and Ruby test suites.
--skip-install: use already-installed dependencies.
--validation-only: run static contract validation and Python syntax compilation.
USAGE
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\n===== %s =====\n' "$1"; }
failures=()
missing=()
record_missing() {
  missing+=("$1")
  printf 'SKIPPED: %s\n' "$2" >&2
}
record_failure() {
  failures+=("$1")
  printf 'FAILED: %s\n' "$1" >&2
}
find_python() {
  local candidate
  for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" --version >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}
require_runtime() {
  local command_name="$1"
  local install_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    record_missing "$command_name" "Install $command_name ($install_hint) and rerun the local CI script."
    return 1
  fi
  return 0
}

step "Static catalog and contract validation"
PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  record_missing "Python" "Install Python 3.10+ and ensure python.exe is on PATH."
else
  if ! "$PYTHON_BIN" scripts/validate-catalog.py ||
    ! "$PYTHON_BIN" scripts/validate-oscu-contract.py ||
    ! "$PYTHON_BIN" -m py_compile \
      scripts/validate-catalog.py \
      scripts/validate-oscu-contract.py \
      scripts/validate-production-config.py \
      scripts/summarize-junit.py \
      scripts/run-oscu-sandbox-check.py \
      server/app/*.py \
      languages/python/*.py; then
    record_failure "Static catalog, contract, or Python syntax validation"
  fi
fi

if [[ "$ONLY_VALIDATION" -eq 0 ]]; then
  step "Python reference API and Python OSCU SDK"
  if [[ -z "$PYTHON_BIN" ]]; then
    record_missing "Python tests" "Install Python 3.10+ and rerun."
  elif [[ "$SKIP_INSTALL" -eq 0 ]] && {
    ! "$PYTHON_BIN" -m pip install -r server/requirements-dev.txt ||
    ! "$PYTHON_BIN" -m pip install -r languages/python/requirements.txt;
  }; then
    record_failure "Python dependency installation"
  elif ! (
    cd server
    ruff check .
    mkdir -p reports
    PYTHONPATH=. pytest -q --junitxml=reports/python-junit.xml
    PYTHONPATH=../languages/python pytest -q ../languages/python --junitxml=reports/python-oscu-sdk-junit.xml
  ); then
    record_failure "Python reference API or OSCU SDK tests"
  fi

  step "Go"
  if require_runtime go "https://go.dev/dl/"; then
    if ! (cd languages/go && go test ./...); then
      record_failure "Go tests"
    fi
  fi

  step "Java"
  if require_runtime java "https://adoptium.net/" &&
    require_runtime mvn "https://maven.apache.org/install.html"; then
    if ! (cd languages/java && mvn -B test); then
      record_failure "Java tests"
    fi
  fi

  step "JavaScript"
  if require_runtime node "https://nodejs.org/" &&
    require_runtime npm "https://nodejs.org/"; then
    if ! (
      cd languages/javascript
      if [[ "$SKIP_INSTALL" -eq 0 ]]; then npm install --no-audit --no-fund; fi
      npm test
    ); then
      record_failure "JavaScript tests"
    fi
  fi

  step "TypeScript build and tests"
  if require_runtime node "https://nodejs.org/" &&
    require_runtime npm "https://nodejs.org/"; then
    if ! (
      cd languages/typescript
      if [[ "$SKIP_INSTALL" -eq 0 ]]; then npm install --no-audit --no-fund; fi
      npm test
    ); then
      record_failure "TypeScript build or tests"
    fi
  fi

  step "PHP"
  if require_runtime php "https://www.php.net/downloads.php" &&
    require_runtime composer "https://getcomposer.org/download/"; then
    if ! (
      cd languages/php
      if [[ "$SKIP_INSTALL" -eq 0 ]]; then composer install --no-interaction --prefer-dist; fi
      composer test
      find src public tests -name '*.php' -print0 | xargs -0 -n1 php -l
    ); then
      record_failure "PHP tests or syntax checks"
    fi
  fi

  step "Ruby"
  if require_runtime ruby "https://www.ruby-lang.org/en/documentation/installation/" &&
    require_runtime bundle "https://bundler.io/guides/getting_started.html"; then
    if ! (
      cd languages/ruby
      if [[ "$SKIP_INSTALL" -eq 0 ]]; then bundle install; fi
      bundle exec rspec
      ruby -c app.rb
      ruby -c oscu_client.rb
    ); then
      record_failure "Ruby tests or syntax checks"
    fi
  fi

  step "Docker Compose configuration"
  if command -v docker >/dev/null 2>&1; then
    if ! (
      created_env_files=()
      cleanup_env_files() {
        local env_file
        for env_file in "${created_env_files[@]}"; do
          rm -f "$env_file"
        done
      }
      trap cleanup_env_files EXIT
      for env_file in .env languages/go/.env languages/java/.env languages/javascript/.env \
        languages/typescript/.env languages/php/.env languages/ruby/.env; do
        if [[ ! -f "$env_file" ]]; then
          : > "$env_file"
          created_env_files+=("$env_file")
        fi
      done
      export REDIS_PASSWORD="local-ci-redis-password"
      export IDEMPOTENCY_ENCRYPTION_KEY="9vN8QxQJ7X2K7Q6q4m0hV3b1l9s8d7f6"
      docker compose config --quiet &&
        docker compose -f docker-compose.multilang.yml config --quiet
    ); then
      record_failure "Docker Compose configuration validation"
    fi
  else
    record_missing "Docker Compose" "Install Docker Desktop or Docker Engine with Compose v2."
  fi
fi

echo
if [[ "${#missing[@]}" -gt 0 || "${#failures[@]}" -gt 0 ]]; then
  echo "Local CI completed with unavailable or failing checks."
  if [[ "${#missing[@]}" -gt 0 ]]; then
    printf 'Unavailable: %s\n' "${missing[*]}"
  fi
  if [[ "${#failures[@]}" -gt 0 ]]; then
    printf 'Failed: %s\n' "${failures[*]}"
  fi
  echo "Install the reported runtimes or fix the failures, then rerun this script."
  exit 1
fi
echo "All configured local CI checks completed successfully."
echo "This validates code and local test fixtures only; it does not prove KRA sandbox access, certification, or production approval."
