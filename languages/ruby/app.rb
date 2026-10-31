require 'json'
require 'rack'
require 'net/http'
require 'uri'
require 'base64'
require 'openssl'
require 'thread'
class KraPinApp
 def initialize
  @env=ENV.fetch('KRA_ENVIRONMENT','sandbox');@mock=ENV.fetch('KRA_MOCK','true')=='true';raise 'Mock mode forbidden in production' if @mock&&@env=='production'
  @base=@env=='production'?'https://api.kra.go.ke':'https://sbx.kra.go.ke';@keys=ENV.fetch('PROXY_API_KEYS','').split(',').map(&:strip).reject(&:empty?);raise 'PROXY_API_KEYS required' if @keys.empty?;@cache={};@hits={};@mutex=Mutex.new
 end
 def call(env)
  req=Rack::Request.new(env);path=req.path
  return reply(200,{status:'ok',environment:@env,mock:@mock}) if req.get?&&path=='/health'
  return reply(404,{detail:'Not found'}) unless req.post?&&['/v1/pin/verify','/v1/pin/verify-by-id'].include?(path)
  key=req.get_header('HTTP_X_API_KEY').to_s;valid=@keys.any?{|x|x.bytesize==key.bytesize&&secure_equal(x,key)};return reply(401,{detail:'Invalid or missing X-API-Key'}) unless valid
  return reply(429,{detail:'Rate limit exceeded'}) unless rate(key)
  begin
   raw=req.body.read(65_537);return reply(413,{detail:'Request too large'}) if raw.bytesize>65_536;b=JSON.parse(raw.empty? ? '{}' : raw);return reply(422,{detail:'JSON object required'}) unless b.is_a?(Hash);id=path.end_with?('verify-by-id');return reply(400,{detail:'consent must be true'}) if ENV.fetch('REQUIRE_CONSENT','true')!='false'&&b['consent']!=true
   value=(id ? b['taxpayer_id'] : b['pin']).to_s.strip.upcase;return reply(422,{detail:'Invalid identifier format'}) if value.length<(id ? 5 : 9)||value.length>20||value !~ /\A[A-Z0-9]+\z/
   reply(200,lookup(id,value,(b['taxpayer_type']||'KE').upcase))
  rescue JSON::ParserError;reply(422,{detail:'Invalid JSON'})
  rescue StandardError;reply(502,{error:{code:'upstream_error',message:'KRA request failed'}})
  end
 end
 private
 def reply(status,data);[status,{'content-type'=>'application/json'},[JSON.generate(data)]];end
 def secure_equal(a,b);OpenSSL.fixed_length_secure_compare(a,b);rescue;false;end
 def rate(key);@mutex.synchronize{now=Time.now.to_f;q=(@hits[key]||[]).select{|t|now-t<60};return false if q.size>=30;q<<now;@hits[key]=q;true};end
 def token(key,secret)
  old=@cache[key];return old[:value] if old&&old[:expires]>Time.now.to_i+60
  uri=URI("#{@base}/v1/token/generate?grant_type=client_credentials");req=Net::HTTP::Get.new(uri);req.basic_auth(key,secret);res=Net::HTTP.start(uri.hostname,uri.port,use_ssl:true,open_timeout:5,read_timeout:15){|h|h.request(req)};d=JSON.parse(res.body);raise 'KRA token request failed' unless res.is_a?(Net::HTTPSuccess)&&d['access_token'];@cache[key]={value:d['access_token'],expires:Time.now.to_i+d.fetch('expires_in',3600).to_i};@cache[key][:value]
 end
 def lookup(id,value,type)
  if @mock;found=id ? value=='00000000' : value=='A000000000B';return {found:found,pin:found ? 'A000000000B' : nil,taxpayer_name:found ? 'DEMO T*****' : nil,environment:@env,mock:true,raw:nil};end
  key=ENV.fetch(id ? 'KRA_PIN_BY_ID_CONSUMER_KEY' : 'KRA_PIN_CONSUMER_KEY',ENV.fetch('KRA_PIN_CONSUMER_KEY',''));secret=ENV.fetch(id ? 'KRA_PIN_BY_ID_CONSUMER_SECRET' : 'KRA_PIN_CONSUMER_SECRET',ENV.fetch('KRA_PIN_CONSUMER_SECRET',''));t=token(key,secret);path=id ? '/checker/v1/pin' : '/checker/v1/pinbypin';payload=id ? {TaxpayerType:type,TaxpayerID:value} : {KRAPIN:value};uri=URI("#{@base}#{path}");req=Net::HTTP::Post.new(uri);req['Authorization']="Bearer #{t}";req['Content-Type']='application/json';req.body=JSON.generate(payload);res=Net::HTTP.start(uri.hostname,uri.port,use_ssl:true,open_timeout:5,read_timeout:15){|h|h.request(req)};d=JSON.parse(res.body)
  return {found:false,pin:nil,taxpayer_name:nil,environment:@env,mock:false,raw:nil} if res.code.to_i==404||d['errorCode'].to_s=='30002';rec=d['PINDATA']||d;pin=rec['KRAPIN'];name=rec['Name'];raise 'Unexpected KRA response' unless res.is_a?(Net::HTTPSuccess)&&(pin||name);{found:true,pin:pin,taxpayer_name:name,environment:@env,mock:false,raw:nil}
 end
end
