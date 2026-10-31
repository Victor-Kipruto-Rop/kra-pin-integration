<?php
// Server-side PHP (Laravel, WordPress plugin back end, plain PHP). Untested sketch; see docs/integration-guides.md.
// PROXY_URL=http://localhost:8000 PROXY_API_KEY=dev-key php verify.php A000000000B
$proxyUrl = getenv('PROXY_URL') ?: 'http://localhost:8000';
$apiKey   = getenv('PROXY_API_KEY') ?: '';
$pin      = $argv[1] ?? 'A000000000B';

$ch = curl_init("$proxyUrl/v1/pin/verify");
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 20,
    CURLOPT_HTTPHEADER     => ["X-API-Key: $apiKey", 'Content-Type: application/json'],
    CURLOPT_POSTFIELDS     => json_encode(['pin' => $pin, 'consent' => true]),
]);
$response = curl_exec($ch);
$status   = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

$body = json_decode($response, true);
if ($status !== 200) {
    fwrite(STDERR, "$status: $response\n");
    exit(1);
}
echo ($body['found'] ? 'KRA PIN found' : 'KRA PIN not found') . PHP_EOL;
