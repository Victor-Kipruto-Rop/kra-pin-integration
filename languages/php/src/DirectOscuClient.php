<?php
declare(strict_types=1);

namespace KraPin;

use RuntimeException;

/** Server-side client for KRA direct eTIMS OSCU sandbox operations. */
final class DirectOscuClient
{
    private const TOKEN_URL = 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials';
    private const API_BASE = 'https://sbx.kra.go.ke/etims-oscu/api/v1';
    private array $operations = [];
    private ?string $accessToken = null;
    private int $tokenExpiresAt = 0;

    /** @param callable|null $transport Test transport: fn(url, headers, body, timeout): array{status:int,body:string} */
    public function __construct(
        private readonly string $consumerKey,
        private readonly string $consumerSecret,
        private readonly string $appId,
        private readonly int $timeoutSeconds = 20,
        private readonly mixed $transport = null,
    ) {
        if ($consumerKey === '' || $consumerSecret === '' || $appId === '') {
            throw new RuntimeException('OSCU consumer credentials and app ID are required');
        }
        if ($timeoutSeconds < 1) throw new RuntimeException('timeout must be positive');
        $manifest = json_decode((string) file_get_contents(__DIR__ . '/etims_oscu_endpoints.json'), true, 512, JSON_THROW_ON_ERROR);
        foreach ($manifest['operations'] as $operation) $this->operations[$operation['id']] = $operation;
    }

    public function operationCount(): int { return count($this->operations); }

    /** @param array<string,mixed> $payload @param array<string,string> $tenantContext */
    public function invoke(string $operationId, array $payload, array $tenantContext = [], bool $confirmMutation = false): mixed
    {
        $operation = $this->operations[$operationId] ?? null;
        if ($operation === null) throw new RuntimeException('Unknown OSCU operation ID');
        if (($operation['mutates'] ?? false) && !$confirmMutation) {
            throw new RuntimeException('Operation may mutate KRA state; explicit confirmation required');
        }
        $headers = [
            'apigee_app_id' => $this->appId,
            'Accept' => 'application/json',
            'Content-Type' => 'application/json',
        ];
        foreach ($operation['headers'] as $name) {
            if ($name === 'apigee_app_id') continue;
            if (empty($tenantContext[$name])) throw new RuntimeException('Missing required OSCU context: ' . $name);
            $headers[$name] = $tenantContext[$name];
        }
        $headers['Authorization'] = 'Bearer ' . $this->accessToken();
        $encoded = json_encode($payload, JSON_THROW_ON_ERROR);
        try {
            $response = $this->request(self::API_BASE . $operation['path'], $headers, $encoded);
        } catch (\Throwable $error) {
            if ($operation['mutates']) {
                throw new OscuUnknownOutcomeException('KRA OSCU request outcome is unknown; reconcile before resubmitting', 0, $error);
            }
            throw new RuntimeException('Could not reach KRA OSCU', 0, $error);
        }
        if ($response['status'] < 200 || $response['status'] >= 300) {
            throw new RuntimeException('KRA OSCU rejected request (HTTP ' . $response['status'] . ')');
        }
        if (trim($response['body']) === '') return null;
        try { return json_decode($response['body'], true, 512, JSON_THROW_ON_ERROR); }
        catch (\JsonException $error) { throw new RuntimeException('KRA OSCU returned non-JSON content', 0, $error); }
    }

    private function accessToken(): string
    {
        if ($this->accessToken !== null && time() < $this->tokenExpiresAt - 60) return $this->accessToken;
        $basic = base64_encode($this->consumerKey . ':' . $this->consumerSecret);
        $response = $this->request(self::TOKEN_URL, [
            'Authorization' => 'Basic ' . $basic,
            'Accept' => 'application/json',
        ], null);
        if ($response['status'] < 200 || $response['status'] >= 300) throw new RuntimeException('KRA rejected OSCU token request');
        $body = json_decode($response['body'], true);
        $token = $body['access_token'] ?? null;
        if (!is_string($token) || $token === '') throw new RuntimeException('KRA returned an invalid OSCU token response');
        $ttl = (int) ($body['expires_in'] ?? 3600);
        $this->accessToken = $token;
        $this->tokenExpiresAt = time() + ($ttl > 0 ? $ttl : 3600);
        return $token;
    }

    private function request(string $url, array $headers, ?string $body): array
    {
        if (is_callable($this->transport)) return ($this->transport)($url, $headers, $body, $this->timeoutSeconds);
        if (!function_exists('curl_init')) throw new RuntimeException('PHP cURL extension is required');
        $curl = curl_init($url);
        $headerLines = [];
        foreach ($headers as $name => $value) $headerLines[] = $name . ': ' . $value;
        curl_setopt_array($curl, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => ($body === null ? 'GET' : 'POST'),
            CURLOPT_HTTPHEADER => $headerLines,
            CURLOPT_CONNECTTIMEOUT => min(10, $this->timeoutSeconds),
            CURLOPT_TIMEOUT => $this->timeoutSeconds,
        ]);
        if ($body !== null) curl_setopt($curl, CURLOPT_POSTFIELDS, $body);
        $responseBody = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        $error = curl_error($curl);
        curl_close($curl);
        if ($responseBody === false) throw new RuntimeException('HTTP transport failed: ' . $error);
        return ['status' => $status, 'body' => (string) $responseBody];
    }
}

final class OscuUnknownOutcomeException extends RuntimeException {}
