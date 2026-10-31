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

 it 'requires consent and idempotency for mutating catalog operations' do
  app=KraPinApp.new
  call=->(id,body,idem=nil){env={'REQUEST_METHOD'=>'POST','PATH_INFO'=>"/v1/kra/#{id}",'HTTP_X_API_KEY'=>'ci-test-key','rack.input'=>StringIO.new(body)};env['HTTP_IDEMPOTENCY_KEY']=idem if idem;app.call(env)}
  expect(call.call('pin-checker-by-pin',JSON.generate(consent:false,payload:{})).first).to eq(400)
  expect(call.call('nil-return-filing',JSON.generate(consent:true,payload:{})).first).to eq(400)
  expect(call.call('pin-checker-by-pin',JSON.generate(consent:true,payload:{})).first).to eq(501)
 end
