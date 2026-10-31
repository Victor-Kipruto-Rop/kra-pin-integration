package ke.co.krapin.oscu;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

/** Server-side client for KRA direct eTIMS OSCU sandbox operations. */
public final class DirectOscuClient {
    private static final String TOKEN_URL = "https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials";
    private static final String API_BASE = "https://sbx.kra.go.ke/etims-oscu/api/v1";
    private final String consumerKey;
    private final String consumerSecret;
    private final String appId;
    private final HttpClient http;
    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, JsonNode> operations = new HashMap<>();
    private String accessToken;
    private Instant tokenExpiresAt = Instant.EPOCH;

    public DirectOscuClient(String consumerKey, String consumerSecret, String appId) throws IOException {
        this(consumerKey, consumerSecret, appId, HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build());
    }

    public DirectOscuClient(String consumerKey, String consumerSecret, String appId, HttpClient http) throws IOException {
        if (consumerKey == null || consumerKey.isBlank() || consumerSecret == null || consumerSecret.isBlank() || appId == null || appId.isBlank()) {
            throw new IllegalArgumentException("OSCU consumer credentials and app ID are required");
        }
        this.consumerKey = consumerKey;
        this.consumerSecret = consumerSecret;
        this.appId = appId;
        this.http = http;
        try (InputStream stream = DirectOscuClient.class.getResourceAsStream("/etims_oscu_endpoints.json")) {
            if (stream == null) throw new IOException("Packaged OSCU endpoint manifest is missing");
            JsonNode root = mapper.readTree(stream);
            for (JsonNode operation : root.path("operations")) operations.put(operation.path("id").asText(), operation);
        }
    }

    public int operationCount() { return operations.size(); }

    public JsonNode invoke(String operationId, Map<String, Object> payload, Map<String, String> tenantContext, boolean confirmMutation)
            throws IOException, InterruptedException {
        JsonNode operation = operations.get(operationId);
        if (operation == null) throw new IllegalArgumentException("Unknown OSCU operation ID");
        if (payload == null) throw new IllegalArgumentException("payload must be a JSON object");
        if (operation.path("mutates").asBoolean() && !confirmMutation) {
            throw new IllegalArgumentException("Operation may mutate KRA state; explicit confirmation required");
        }
        Map<String, String> headers = new HashMap<>();
        headers.put("apigee_app_id", appId);
        headers.put("Accept", "application/json");
        headers.put("Content-Type", "application/json");
        for (JsonNode header : operation.path("headers")) {
            String name = header.asText();
            if ("apigee_app_id".equals(name)) continue;
            String value = tenantContext == null ? null : tenantContext.get(name);
            if (value == null || value.isBlank()) throw new IllegalArgumentException("Missing required OSCU context: " + name);
            headers.put(name, value);
        }

        String token = token();
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(API_BASE + operation.path("path").asText()))
                .timeout(Duration.ofSeconds(20))
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(payload)));
        headers.forEach(builder::header);
        builder.header("Authorization", "Bearer " + token);
        HttpResponse<String> response;
        try {
            response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        } catch (IOException ex) {
            if (operation.path("mutates").asBoolean()) throw new UnknownOutcomeException();
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            if (operation.path("mutates").asBoolean()) throw new UnknownOutcomeException();
            throw ex;
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            if (operation.path("mutates").asBoolean() && response.statusCode() >= 500) {
                throw new UnknownOutcomeException();
            }
            throw new IOException("KRA OSCU rejected request (HTTP " + response.statusCode() + ")");
        }
        if (response.body() == null || response.body().isBlank()) return null;
        try {
            return mapper.readTree(response.body());
        } catch (Exception ex) {
            if (operation.path("mutates").asBoolean()) throw new UnknownOutcomeException();
            throw new IOException("KRA OSCU returned a non-JSON response");
        }
    }

    private synchronized String token() throws IOException, InterruptedException {
        if (accessToken != null && Instant.now().isBefore(tokenExpiresAt.minusSeconds(60))) return accessToken;
        String basic = Base64.getEncoder().encodeToString((consumerKey + ":" + consumerSecret).getBytes(StandardCharsets.UTF_8));
        HttpRequest request = HttpRequest.newBuilder(URI.create(TOKEN_URL))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", "Basic " + basic)
                .GET().build();
        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) throw new IOException("KRA rejected OSCU token request");
        JsonNode body = mapper.readTree(response.body());
        String token = body.path("access_token").asText();
        if (token.isBlank()) throw new IOException("KRA returned an invalid OSCU token response");
        long ttl = body.path("expires_in").asLong(3600);
        if (ttl <= 0) ttl = 3600;
        accessToken = token;
        tokenExpiresAt = Instant.now().plusSeconds(ttl);
        return token;
    }

    public static final class UnknownOutcomeException extends IOException {
        public UnknownOutcomeException() {
            super("KRA OSCU request outcome is unknown; reconcile before resubmitting");
        }
    }
}
