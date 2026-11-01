# Per-service KRA implementation status

The proxy exposes stable service IDs for the full developer-catalog list. This document separates **catalog coverage** from **verified upstream implementation**.

- Catalog registration: implemented in all seven templates.
- Request/response schema: being added as official per-service Postman contracts are supplied; response examples remain outstanding for the two documented GavaConnect services.
- Upstream path and HTTP method: configured only for services with supplied official GavaConnect Postman contracts; all others remain intentionally unconfigured.
- Sandbox verification: not yet performed; approved application credentials and test data are required.

Do not infer API paths, scopes, request fields, response fields, not-found codes or mutation semantics from the service display names.

| Catalog service | Stable ID | Upstream contract status |
|---|---|---|
| Authorization | `authorization` | Awaiting official specification and sandbox test |
| PIN Checker by PIN | `pin-checker-by-pin` | Awaiting official specification and sandbox test |
| PIN Checker BY ID | `pin-checker-by-id` | Awaiting official specification and sandbox test |
| Fetch Taxpayer Obligations | `fetch-taxpayer-obligations` | Postman contract supplied; sandbox execution still pending |
| Know KRA Tax Service Office | `know-kra-tax-service-office` | Awaiting official specification and sandbox test |
| Tax Compliance Certificate Application | `tax-compliance-certificate-application` | Awaiting official specification and sandbox test |
| Tax Compliance Certificate Checker | `tax-compliance-certificate-checker` | Awaiting official specification and sandbox test |
| VAT Exemption Checker | `vat-exemption-checker` | Postman contract supplied; sandbox execution still pending |
| IT Exemption checker | `it-exemption-checker` | Awaiting official specification and sandbox test |
| NIL Return Filling | `nil-return-filing` | Awaiting official specification and sandbox test |
| TOT Return Filing | `tot-return-filing` | Awaiting official specification and sandbox test |
| Income Tax Withholding PRN Generation | `income-tax-withholding-prn-generation` | Awaiting official specification and sandbox test |
| VAT Withholding PRN Generation | `vat-withholding-prn-generation` | Awaiting official specification and sandbox test |
| Rental Withholding PRN Generation | `rental-withholding-prn-generation` | Awaiting official specification and sandbox test |
| Excise License Checker By Pin | `excise-license-checker-by-pin` | Awaiting official specification and sandbox test |
| Excise License Checker By Certificate Number | `excise-license-checker-by-certificate-number` | Awaiting official specification and sandbox test |
| Customs Declaration Status Checker | `customs-declaration-status-checker` | Awaiting official specification and sandbox test |
| Customs Tax Calculator | `customs-tax-calculator` | Awaiting official specification and sandbox test |
| Import Certificate Checker by PIN | `import-certificate-checker-by-pin` | Awaiting official specification and sandbox test |
| Import Certificate Checker by Cert Number | `import-certificate-checker-by-cert-number` | Awaiting official specification and sandbox test |
| Invoice Checker | `invoice-checker` | Awaiting official specification and sandbox test |
| eTIMS OSCU Integrator Automated Testing | `etims-oscu-integrator-automated-testing` | Awaiting official GavaConnect specification and sandbox test |

## Required evidence for each service

Before enabling a service in a live deployment, record:
1. KRA developer application subscription and OAuth scope/permission.
2. Official specification version/date and exact base URL, relative path and HTTP method.
3. Exact request schema, required fields, formats, enums, limits and validation rules.
4. Success, validation-error, not-found, unauthorized, rate-limit and server-error response examples.
5. Whether the operation mutates taxpayer records, generates a PRN, or can be safely retried.
6. Idempotency/replay rules and how to query the outcome after a timeout.
7. Redacted sandbox request/response evidence and automated contract tests in all seven runtimes.
8. Production access approval, operational monitoring and rollback procedure.

## Mapping configuration

Use `contracts/kra-service-mappings.template.json` as the GavaConnect catalog inventory. Empty paths intentionally return HTTP 501. Populate `KRA_SERVICE_PATHS_JSON` and `KRA_SERVICE_METHODS_JSON` from verified documentation; do not deploy placeholder paths.

## Direct eTIMS OSCU integration (separate from the catalog)

A supplied Postman collection now documents a separate direct OSCU sandbox endpoint inventory: [`contracts/etims-oscu-direct.endpoints.json`](../contracts/etims-oscu-direct.endpoints.json), with notes in [the direct OSCU integration guide](etims-oscu-direct-integration.md). It contains 23 POST operations under `https://sbx.kra.go.ke/etims-oscu/api/v1`. The Python server includes a separate sandbox-only direct OSCU adapter. Seven server-side SDK clients (Python, Go, Java, JavaScript, TypeScript, PHP and Ruby) share the canonical 23-operation manifest, with parity checked by CI. Formal request/response schemas, live sandbox execution and certification remain outstanding.

Do not populate the GavaConnect catalog service mapping with direct OSCU paths. The two systems have separate base URLs, authentication contexts and operational lifecycles. Never forward a GavaConnect bearer token to the direct OSCU host.

The direct OSCU collection contains sample-quality issues that must be resolved before use, including invalid JSON comments and the malformed sales property `isr ccCd`. Confirm these with KRA rather than silently correcting them.

KRA's direct OSCU/VSCU device-protocol integration requires its own sandbox testing and certification. See the official [OSCU specification](https://www.kra.go.ke/images/publications/OSCU_Specification_Document_v2.0.pdf), [OSCU/VSCU sign-up guide](https://kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf), and [KRA system-to-system integration guidance](https://www.kra.go.ke/services/service/16).
