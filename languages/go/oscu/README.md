# Go direct eTIMS OSCU SDK

Package `oscu` is a server-side KRA direct OSCU sandbox client. It uses a fixed sandbox host, HTTP Basic token acquisition and bearer-authenticated POST operations.

Create a client with `oscu.NewClient(consumerKey, consumerSecret, appID, httpClient)`, then call `Invoke(ctx, operationID, payload, tenantContext, confirmMutation)`. Mutating operations require explicit confirmation. The client never retries submitted requests; an uncertain mutation must be reconciled with KRA before resubmission.

Request/response schemas and mutation classifications remain provisional because the supplied Postman collection does not contain formal contracts. Production hosts are intentionally unsupported.
