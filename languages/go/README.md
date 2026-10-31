# Go service

Go 1.22+ standard-library HTTP service. Run `go test ./...` then `go run .`. Configure variables from `.env.example`; mock PIN is `A000000000B`, mock ID `00000000`. Independent KRA integration. In-memory cache/rate limit is per process. Confirm KRA response mappings in sandbox before production.
