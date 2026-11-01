require 'stringio'
ENV['PROXY_API_KEYS'] ||= 'ci-test-key'
ENV['KRA_MOCK'] ||= 'true'
ENV['KRA_ENVIRONMENT'] ||= 'sandbox'
ENV['REQUIRE_CONSENT'] ||= 'true'
require_relative '../app'
RSpec.describe KraPinApp do
 it 'declares all 22 catalog services' do
  expect(SERVICE_MUTATES.size).to eq(22)
 end

 it 'returns a health response' do
  status,headers,body=KraPinApp.new.call({'REQUEST_METHOD'=>'GET','PATH_INFO'=>'/health'})
  expect(status).to eq(200);expect(headers['content-type']).to include('application/json');expect(body.join).to include('"status":"ok"')
 end
end

RSpec.describe KraPinApp do
 it 'requires consent and idempotency for mutating catalog operations' do
  app=KraPinApp.new
  call=->(id,body,idem=nil){env={'REQUEST_METHOD'=>'POST','PATH_INFO'=>"/v1/kra/#{id}",'HTTP_X_API_KEY'=>'ci-test-key','rack.input'=>StringIO.new(body)};env['HTTP_IDEMPOTENCY_KEY']=idem if idem;app.call(env)}
  expect(call.call('pin-checker-by-pin',JSON.generate(consent:false,payload:{})).first).to eq(400)
  expect(call.call('nil-return-filing',JSON.generate(consent:true,payload:{})).first).to eq(400)
  expect(call.call('pin-checker-by-pin',JSON.generate(consent:true,payload:{})).first).to eq(501)
 end
end


RSpec.describe KraPinApp do
 it 'blocks duplicate catalog mutations after an ambiguous upstream failure' do
  previous_env=ENV.to_hash
  begin
   ENV['KRA_MOCK']='false'
   ENV['KRA_ENVIRONMENT']='sandbox'
   ENV['KRA_PIN_CONSUMER_KEY']='consumer'
   ENV['KRA_PIN_CONSUMER_SECRET']='secret'
   ENV['KRA_SERVICE_PATHS_JSON']=JSON.generate('nil-return-filing'=>'/filing')
   ENV['KRA_SERVICE_METHODS_JSON']='{}'
   app=KraPinApp.new
   allow(app).to receive(:token).and_return('token')
   response=Net::HTTPBadGateway.new('1.1','502','Bad Gateway')
   response.instance_variable_set(:@body,'{"error":"temporary"}')
   response.instance_variable_set(:@read,true)
   expect(app).to receive(:upstream_request).once.and_return(response)
   call=-> {
    app.call({
     'REQUEST_METHOD'=>'POST',
     'PATH_INFO'=>'/v1/kra/nil-return-filing',
     'HTTP_X_API_KEY'=>'ci-test-key',
     'HTTP_IDEMPOTENCY_KEY'=>'ruby-mutation-unknown-001',
     'rack.input'=>StringIO.new(JSON.generate(consent:true,payload:{period:'2026'}))
    })
   }
   expect(call.call.first).to eq(502)
   replay=call.call
   expect(replay.first).to eq(409)
   expect(replay.last.join).to include('idempotency_outcome_unknown')
  ensure
   ENV.replace(previous_env)
  end
 end
end
