import { readFileSync } from 'node:fs';
import { Buffer } from 'node:buffer';

const TOKEN_URL = 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials';
const API_BASE = 'https://sbx.kra.go.ke/etims-oscu/api/v1';

type Operation = { id: string; method: string; path: string; headers: string[]; mutates: boolean };
type Manifest = { operations: Operation[] };
const manifest = JSON.parse(readFileSync(new URL('./etims_oscu_endpoints.json', import.meta.url), 'utf8')) as Manifest;

export class OscuError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly outcomeUnknown = false,
  ) {
    super(message);
    this.name = 'OscuError';
  }
}

export type OscuClientOptions = {
  consumerKey: string;
  consumerSecret: string;
  appId: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
};

export type TenantContext = { tin?: string; bhfId?: string; cmcKey?: string };

/** Server-side only KRA direct OSCU sandbox client. */
export class DirectOscuClient {
  private readonly operations = new Map(manifest.operations.map(operation => [operation.id, operation]));
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private accessToken?: string;
  private tokenExpiresAt = 0;

  constructor(private readonly options: OscuClientOptions) {
    if (!options.consumerKey || !options.consumerSecret || !options.appId) {
      throw new TypeError('OSCU consumer credentials and app ID are required');
    }
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 20_000;
  }

  operationCount(): number { return this.operations.size; }

  private async getAccessToken(): Promise<string> {
    if (this.accessToken && Date.now() < this.tokenExpiresAt - 60_000) return this.accessToken;
    try {
      const basic = Buffer.from(`${this.options.consumerKey}:${this.options.consumerSecret}`).toString('base64');
      const response = await this.fetchImpl(TOKEN_URL, {
        method: 'GET',
        headers: { Authorization: `Basic ${basic}`, Accept: 'application/json' },
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      if (!response.ok) throw new Error('token request rejected');
      const body = await response.json() as { access_token?: unknown; expires_in?: unknown };
      if (typeof body.access_token !== 'string' || !body.access_token) throw new Error('invalid token response');
      this.accessToken = body.access_token;
      const ttl = typeof body.expires_in === 'number' && body.expires_in > 0 ? body.expires_in : 3600;
      this.tokenExpiresAt = Date.now() + ttl * 1000;
      return this.accessToken;
    } catch {
      throw new OscuError('oscu_auth_failed', 'Could not obtain a valid KRA OSCU access token');
    }
  }

  async invoke(
    operationId: string,
    payload: Record<string, unknown>,
    tenantContext: TenantContext = {},
    options: { confirmMutation?: boolean } = {},
  ): Promise<unknown> {
    const operation = this.operations.get(operationId);
    if (!operation) throw new TypeError('Unknown OSCU operation ID');
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new TypeError('payload must be a JSON object');
    if (operation.mutates && options.confirmMutation !== true) {
      throw new TypeError('Operation may mutate KRA state; explicit confirmation required');
    }
    const headers: Record<string, string> = {
      apigee_app_id: this.options.appId,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    };
    for (const name of operation.headers) {
      if (name === 'apigee_app_id') continue;
      const value = tenantContext[name as keyof TenantContext];
      if (!value) throw new TypeError(`Missing required OSCU context: ${name}`);
      headers[name] = value;
    }
    headers.Authorization = `Bearer ${await this.getAccessToken()}`;
    let response: Response;
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
        operation.mutates,
      );
    }
    if (!response.ok) throw new OscuError('oscu_request_rejected', `KRA OSCU rejected request (HTTP ${response.status})`);
    const text = await response.text();
    if (!text.trim()) return null;
    try { return JSON.parse(text) as unknown; }
    catch { throw new OscuError('oscu_invalid_response', 'KRA OSCU returned a non-JSON response'); }
  }
}
