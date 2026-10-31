import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';

process.env.PROXY_API_KEYS = 'ci-test-key';
process.env.KRA_MOCK = 'true';
process.env.KRA_ENVIRONMENT = 'sandbox';
process.env.REQUIRE_CONSENT = 'true';

let server, services, base;
before(async () => {
  ({ server, services } = await import('./server.js'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(async () => { if (server?.listening) await new Promise((resolve, reject) => server.close(e => e ? reject(e) : resolve())); });

const headers = { 'content-type': 'application/json', 'x-api-key': 'ci-test-key' };
test('TypeScript catalog contains exactly 22 services', () => assert.equal(Object.keys(services).length, 22));
test('health is available', async () => { const r=await fetch(base+'/health'); assert.equal(r.status,200); });
test('unknown service is rejected', async () => { const r=await fetch(base+'/v1/kra/not-a-service',{method:'POST',headers,body:JSON.stringify({consent:true,payload:{}})}); assert.equal(r.status,404); });
test('catalog requires API key', async () => { const r=await fetch(base+'/v1/kra/pin-checker-by-pin',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({consent:true,payload:{}})}); assert.equal(r.status,401); });
test('catalog requires explicit consent', async () => { const r=await fetch(base+'/v1/kra/pin-checker-by-pin',{method:'POST',headers,body:JSON.stringify({consent:false,payload:{}})}); assert.equal(r.status,400); });
test('mutating service requires idempotency key', async () => { const r=await fetch(base+'/v1/kra/nil-return-filing',{method:'POST',headers,body:JSON.stringify({consent:true,payload:{}})}); assert.equal(r.status,400); });
test('unimplemented mock operation fails closed', async () => { const r=await fetch(base+'/v1/kra/pin-checker-by-pin',{method:'POST',headers,body:JSON.stringify({consent:true,payload:{}})}); assert.equal(r.status,501); });
