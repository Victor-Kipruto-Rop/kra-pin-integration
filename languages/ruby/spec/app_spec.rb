require_relative '../app'
RSpec.describe KraPinApp do
 it 'returns a health response' do
  status,headers,body=KraPinApp.new.call({'REQUEST_METHOD'=>'GET','PATH_INFO'=>'/health'})
  expect(status).to eq(200);expect(headers['content-type']).to include('application/json');expect(body.join).to include('"status":"ok"')
 end
end
