import test from 'node:test';
import assert from 'node:assert/strict';
import { DirectOscuClient } from './oscu-client.js';

test('registry contains all 23 direct OSCU operations', () => {
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { throw new Error('network disabled'); } });
  assert.equal(client.operations.size, 23);
});

test('unknown operation fails before network', async () => {
  let called = false;
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { called = true; } });
  await assert.rejects(client.invoke('not-real', {}, {}), /Unknown OSCU/);
  assert.equal(called, false);
});

test('mutating operation requires explicit confirmation before network', async () => {
  let called = false;
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl: async () => { called = true; } });
  await assert.rejects(client.invoke('save-item', {}, { tin: 'P1', bhfId: '00', cmcKey: 'x' }), /confirmation/);
  assert.equal(called, false);
});

test('read-only call uses fixed sandbox host and expected headers', async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    if (url.includes('/v1/token/generate')) return { ok: true, json: async () => ({ access_token: 'sandbox-token', expires_in: 3600 }) };
    return { ok: true, status: 200, text: async () => '{"ok":true}' };
  };
  const client = new DirectOscuClient({ consumerKey: 'key', consumerSecret: 'secret', appId: 'app', fetchImpl });
  const result = await client.invoke('branch-list', {}, { tin: 'P123', bhfId: '00', cmcKey: 'branch-secret' });
  assert.deepEqual(result, { ok: true });
  assert.equal(calls[0].url, 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials');
  assert.equal(calls[1].url, 'https://sbx.kra.go.ke/etims-oscu/api/v1/branchList');
  assert.equal(calls[1].options.headers.Authorization, 'Bearer sandbox-token');
  assert.equal(calls[1].options.headers.apigee_app_id, 'app');
});
