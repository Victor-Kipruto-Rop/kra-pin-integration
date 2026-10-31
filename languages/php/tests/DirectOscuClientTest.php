<?php
declare(strict_types=1);

use KraPin\DirectOscuClient;
use PHPUnit\Framework\TestCase;

require_once __DIR__ . '/../src/DirectOscuClient.php';

final class DirectOscuClientTest extends TestCase
{
    public function testManifestContains23Operations(): void
    {
        $client = new DirectOscuClient('key', 'secret', 'app', 20, fn() => ['status' => 200, 'body' => '{}']);
        self::assertSame(23, $client->operationCount());
    }

    public function testUnknownOperationFailsBeforeTransport(): void
    {
        $called = false;
        $client = new DirectOscuClient('key', 'secret', 'app', 20, function () use (&$called) {
            $called = true;
            return ['status' => 200, 'body' => '{}'];
        });
        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('Unknown OSCU');
        $client->invoke('not-real', []);
        self::assertFalse($called);
    }

    public function testMutationRequiresExplicitConfirmation(): void
    {
        $client = new DirectOscuClient('key', 'secret', 'app', 20, fn() => ['status' => 200, 'body' => '{}']);
        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('confirmation');
        $client->invoke('save-item', [], ['tin' => 'P1', 'bhfId' => '00', 'cmcKey' => 'x']);
    }

    public function testReadOnlyOperationUsesSandboxTokenAndHeaders(): void
    {
        $calls = [];
        $transport = function ($url, $headers, $body, $timeout) use (&$calls) {
            $calls[] = compact('url', 'headers', 'body', 'timeout');
            if (str_contains($url, '/v1/token/generate')) return ['status' => 200, 'body' => '{"access_token":"token","expires_in":3600}'];
            return ['status' => 200, 'body' => '{"ok":true}'];
        };
        $client = new DirectOscuClient('key', 'secret', 'app', 20, $transport);
        self::assertSame(['ok' => true], $client->invoke('branch-list', [], ['tin' => 'P123', 'bhfId' => '00', 'cmcKey' => 'ctx']));
        self::assertSame('https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials', $calls[0]['url']);
        self::assertSame('https://sbx.kra.go.ke/etims-oscu/api/v1/branchList', $calls[1]['url']);
        self::assertSame('Bearer token', $calls[1]['headers']['Authorization']);
    }
}
