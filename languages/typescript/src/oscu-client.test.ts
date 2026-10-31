import test from 'node:test';
import assert from 'node:assert/strict';
import { DirectOscuClient } from './oscu-client.js';

test('registry contains 23 OSCU operations', () => {
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { throw new Error('network disabled'); } });
  assert.equal(client.operationCount(), 23);
});

test('unknown operation fails before network', async () => {
  let called = false;
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { called = true; throw new Error('network'); } });
  await assert.rejects(client.invoke('not-real', {}, {}), /Unknown OSCU/);
  assert.equal(called, false);
});

test('mutation requires explicit confirmation before network', async () => {
  let called = false;
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { called = true; throw new Error('network'); } });
  await assert.rejects(client.invoke('save-item', {}, { tin: 'P1', bhfId: '00', cmcKey: 'x' }), /confirmation/);
  assert.equal(called, false);
});

test('read-only operation uses fixed sandbox URLs and bearer auth', async () => {
  const calls: Array<{ url: string; options: RequestInit }> = [];
  const fetchImpl: typeof fetch = async (input, init = {}) => {
    const url = String(input);
    calls.push({ url, options: init });
    if (url.includes('/v1/token/generate')) {
      return new Response(JSON.stringify({ access_token: 'token', expires_in: 3600 }), { status: 200 });
    }
    return new Response('{"ok":true}', { status: 200 });
  };
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl });
  assert.deepEqual(await client.invoke('branch-list', {}, { tin: 'P123', bhfId: '00', cmcKey: 'ctx' }), { ok: true });
  assert.equal(calls[0].url, 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials');
  assert.equal(calls[1].url, 'https://sbx.kra.go.ke/etims-oscu/api/v1/branchList');
  assert.equal((calls[1].options.headers as Record<string, string>).Authorization, 'Bearer token');
});
