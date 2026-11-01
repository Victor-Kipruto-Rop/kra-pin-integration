import test from 'node:test';
import assert from 'node:assert/strict';
import type { AddressInfo } from 'node:net';

test('ambiguous catalog mutation outcome blocks a duplicate submission', async () => {
  const originalFetch = globalThis.fetch;
  const localFetch = originalFetch;
  let operationCalls = 0;
  process.env.PROXY_API_KEYS = 'ci-test-key';
  process.env.KRA_MOCK = 'false';
  process.env.KRA_ENVIRONMENT = 'sandbox';
  process.env.KRA_PIN_CONSUMER_KEY = 'consumer';
  process.env.KRA_PIN_CONSUMER_SECRET = 'secret';
  process.env.KRA_SERVICE_PATHS_JSON = JSON.stringify({ 'nil-return-filing': '/filing' });
  process.env.KRA_SERVICE_METHODS_JSON = '{}';
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    if (String(input).includes('/v1/token/generate')) {
      return new Response(JSON.stringify({ access_token: 'token', expires_in: 3600 }), { status: 200 });
    }
    operationCalls += 1;
    return new Response('{"error":"temporary"}', { status: 503 });
  }) as typeof fetch;
  const { server } = await import('./server.js');
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Expected a TCP listener');
    const base = `http://127.0.0.1:${(address as AddressInfo).port}`;
    const headers = {
      'content-type': 'application/json',
      'x-api-key': 'ci-test-key',
      'idempotency-key': 'catalog-mutation-unknown-001',
    };
    const body = JSON.stringify({ consent: true, payload: { period: '2026' } });
    const first = await localFetch(base + '/v1/kra/nil-return-filing', { method: 'POST', headers, body });
    const replay = await localFetch(base + '/v1/kra/nil-return-filing', { method: 'POST', headers, body });
    assert.equal(first.status, 502);
    assert.equal(replay.status, 409);
    assert.equal((await replay.json() as { error: { code: string } }).error.code, 'idempotency_outcome_unknown');
    assert.equal(operationCalls, 1);
  } finally {
    globalThis.fetch = originalFetch;
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});
