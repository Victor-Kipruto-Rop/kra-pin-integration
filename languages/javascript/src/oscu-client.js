import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const TOKEN_URL = 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials';
const API_BASE = 'https://sbx.kra.go.ke/etims-oscu/api/v1';
const manifestPath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'etims_oscu_endpoints.json');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));

export class OscuError extends Error {
  constructor(code, message, outcomeUnknown = false) {
    super(message);
    this.name = 'OscuError';
    this.code = code;
    this.outcomeUnknown = outcomeUnknown;
  }
}

/** Server-side only KRA direct OSCU sandbox client. */
export class DirectOscuClient {
  constructor({ consumerKey, consumerSecret, appId, fetchImpl = globalThis.fetch, timeoutMs = 20000 }) {
    if (!consumerKey || !consumerSecret || !appId) throw new TypeError('OSCU consumer credentials and app ID are required');
    if (typeof fetchImpl !== 'function') throw new TypeError('A fetch implementation is required');
    this.consumerKey = consumerKey;
    this.consumerSecret = consumerSecret;
    this.appId = appId;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.operations = new Map(manifest.operations.map(operation => [operation.id, operation]));
    this.accessToken = null;
    this.tokenExpiresAt = 0;
  }

  async accessTokenValue() {
    if (this.accessToken && Date.now() < this.tokenExpiresAt - 60000) return this.accessToken;
    let response;
    try {
      const basic = Buffer.from(`${this.consumerKey}:${this.consumerSecret}`).toString('base64');
      response = await this.fetchImpl(TOKEN_URL, {
        method: 'GET',
        headers: { Authorization: `Basic ${basic}`, Accept: 'application/json' },
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      if (!response.ok) throw new Error('token request rejected');
      const body = await response.json();
      if (typeof body.access_token !== 'string' || !body.access_token) throw new Error('invalid token response');
      this.accessToken = body.access_token;
      this.tokenExpiresAt = Date.now() + (Number(body.expires_in) > 0 ? Number(body.expires_in) : 3600) * 1000;
      return this.accessToken;
    } catch {
      throw new OscuError('oscu_auth_failed', 'Could not obtain a valid KRA OSCU access token');
    }
  }

  async invoke(operationId, payload, tenantContext = {}, { confirmMutation = false } = {}) {
    const operation = this.operations.get(operationId);
    if (!operation) throw new TypeError('Unknown OSCU operation ID');
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new TypeError('payload must be a JSON object');
    if (operation.mutates && !confirmMutation) throw new TypeError('Operation may mutate KRA state; explicit confirmation required');

    const headers = { apigee_app_id: this.appId, Accept: 'application/json', 'Content-Type': 'application/json' };
    for (const name of operation.headers) {
      if (name === 'apigee_app_id') continue;
      if (!tenantContext[name]) throw new TypeError(`Missing required OSCU context: ${name}`);
      headers[name] = tenantContext[name];
    }
    headers.Authorization = `Bearer ${await this.accessTokenValue()}`;
    let response;
    try {
      response = await this.fetchImpl(`${API_BASE}${operation.path}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch {
      throw new OscuError(
        operation.mutates ? 'oscu_outcome_unknown' : 'oscu_upstream_unreachable',
        operation.mutates ? 'KRA OSCU request outcome is unknown; reconcile before resubmitting' : 'Could not reach KRA OSCU',
        Boolean(operation.mutates),
      );
    }
    if (!response.ok) throw new OscuError('oscu_request_rejected', `KRA OSCU rejected request (HTTP ${response.status})`);
    const text = await response.text();
    if (!text.trim()) return null;
    try { return JSON.parse(text); }
    catch { throw new OscuError('oscu_invalid_response', 'KRA OSCU returned a non-JSON response'); }
  }
}
