# Architecture

Python FastAPI under server/ is the reference. Go, Java, JavaScript, TypeScript, PHP and Ruby under languages/ are independent server applications and call KRA GavaConnect directly. The caller authenticates with X-API-Key; the service authenticates upstream with KRA consumer credentials. Never expose KRA credentials to clients.

Current upstream routes represented by the Python template: GET /v1/token/generate?grant_type=client_credentials (HTTP Basic), POST /checker/v1/pinbypin with KRAPIN, POST /checker/v1/pin with TaxpayerType and TaxpayerID. Confirm endpoints and response mappings against current developer portal/sandbox documentation.
