require_relative '../oscu_client'

RSpec.describe KraPin::DirectOscuClient do
  def build_client(transport = nil)
    KraPin::DirectOscuClient.new(
      consumer_key: 'key',
      consumer_secret: 'secret',
      app_id: 'app',
      transport: transport
    )
  end

  it 'loads all 23 operations from the packaged manifest' do
    expect(build_client.operations.size).to eq(23)
  end

  it 'rejects unknown operations before network access' do
    called = false
    client = build_client(->(*) { called = true })
    expect { client.invoke('not-real', {}, {}) }.to raise_error(ArgumentError, /Unknown OSCU/)
    expect(called).to be false
  end

  it 'requires explicit confirmation for mutating operations' do
    called = false
    client = build_client(->(*) { called = true })
    expect { client.invoke('save-item', {}, { 'tin' => 'P1', 'bhfId' => '00', 'cmcKey' => 'x' }) }.to raise_error(ArgumentError, /confirmation/)
    expect(called).to be false
  end

  it 'uses the fixed sandbox token and operation URLs with bearer authentication' do
    calls = []
    transport = lambda do |url, headers, body, timeout|
      calls << [url, headers, body, timeout]
      if url.include?('/v1/token/generate')
        { status: 200, body: '{"access_token":"token","expires_in":3600}' }
      else
        { status: 200, body: '{"ok":true}' }
      end
    end
    client = build_client(transport)
    expect(client.invoke('branch-list', {}, { 'tin' => 'P123', 'bhfId' => '00', 'cmcKey' => 'ctx' })).to eq({ 'ok' => true })
    expect(calls[0][0]).to eq('https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials')
    expect(calls[1][0]).to eq('https://sbx.kra.go.ke/etims-oscu/api/v1/branchList')
    expect(calls[1][1]['Authorization']).to eq('Bearer token')
  end

  it 'marks mutating server errors and malformed responses as unknown outcomes' do
    [
      { status: 503, body: '{"error":"temporary"}' },
      { status: 200, body: 'not-json' }
    ].each do |operation_response|
      transport = lambda do |url, _headers, _body, _timeout|
        if url.include?('/v1/token/generate')
          { status: 200, body: '{"access_token":"token","expires_in":3600}' }
        else
          operation_response
        end
      end
      client = build_client(transport)
      expect do
        client.invoke('save-item', { 'itemCd' => 'item-1' },
                      { 'tin' => 'P1', 'bhfId' => '00', 'cmcKey' => 'ctx' },
                      confirm_mutation: true)
      end.to raise_error(KraPin::OscuError) { |error| 
        expect(error.code).to eq('oscu_outcome_unknown')
        expect(error.outcome_unknown).to be true
      }
    end
  end

end