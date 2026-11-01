# CI recovery and contract validation

## Local validation

Run the static inventory checks before the language test suites:

```bash
python scripts/validate-catalog.py
python scripts/validate-oscu-contract.py
python -m py_compile scripts/validate-catalog.py scripts/validate-oscu-contract.py scripts/validate-production-config.py
cd server
python -m pip install -r requirements-dev.txt
ruff check .
PYTHONPATH=. pytest -q
```

Run the language suites with their native toolchains:

- Go: `cd languages/go && go test ./...`
- Java: `cd languages/java && mvn -B test`
- JavaScript: `cd languages/javascript && npm test`
- TypeScript: `cd languages/typescript && npm ci && npm test` (if a lockfile is present; otherwise use `npm install`)
- PHP: `cd languages/php && composer install --no-interaction && composer test`
- Ruby: `cd languages/ruby && bundle install && bundle exec rspec`

## GitLab CI

The repository includes `.gitlab-ci.yml` as a runner alternative. Import or mirror this repository into a GitLab project, enable shared or project runners, and push the branch. A GitLab pipeline cannot be started from this GitHub connection and has not been represented as executed.

The GitLab pipeline runs catalog and OSCU static contract checks before language tests. It retains job-level logs and JUnit output where the test runner supports it.

## GitHub Actions

The GitHub workflows are configured to run on pull requests and pushes (and the multi-language workflow supports manual dispatch). Previous failures reported no executed steps, so they are not evidence of source-level test failures. Check repository Actions availability, billing/usage limits, and runner provisioning before interpreting a failed run as a code test result.

## OSCU validation limits

`scripts/validate-oscu-contract.py` verifies the 23-operation inventory, unique IDs and paths, documented POST methods, header requirements, initialization's special header list, explicit mutation classification, and parity between the canonical contract and the JSON packaged in the server image.

It does **not** prove that KRA accepts the requests. The supplied collection has no formal response schemas and contains a malformed sample property named `isr ccCd`; this remains unresolved pending written KRA confirmation. Mutation classification also requires confirmation. No live sandbox test or certification is implied by a passing static validator.
