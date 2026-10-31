require 'json'
require 'rack'
require 'net/http'
require 'uri'
require 'base64'
require 'openssl'
require 'thread'
require 'digest'

SERVICE_MUTATES = {
 'authorization'=>false,'pin-checker-by-pin'=>false,'pin-checker-by-id'=>false,
 'fetch-taxpayer-obligations'=>false,'know-kra-tax-service-office'=>false,
 'tax-compliance-certificate-application'=>true,'tax-compliance-certificate-checker'=>false,
 'vat-exemption-checker'=>false,'it-exemption-checker'=>false,'nil-return-filing'=>true,
 'tot-return-filing'=>true,'income-tax-withholding-prn-generation'=>true,
 'vat-withholding-prn-generation'=>true,'rental-withholding-prn-generation'=>true,
 'excise-license-checker-by-pin'=>false,'excise-license-checker-by-certificate-number'=>false,
 'customs-declaration-status-checker'=>false,'customs-tax-calculator'=>false,
 'import-certificate-checker-by-pin'=>false,'import-certificate-checker-by-cert-number'=>false,
 'invoice-checker'=>false,'etims-oscu-integrator-automated-testing'=>true
}.freeze

class KraPinApp
 def initialize
  @env=ENV.fetch('KRA_ENVIRONMENT','sandbox');raise 'KRA_ENVIRONMENT must be sandbox or production' unless ['sandbox','production'].include?(@env);@mock=ENV.fetch('KRA_MOCK','true')=='true';raise 'Mock mode forbidden in production' if @mock&&@env=='production';raise 'KRA credentials required when mock mode is disabled' if !@mock&&(ENV.fetch('KRA_PIN_CONSUMER_KEY','').empty?||ENV.fetch('KRA_PIN_CONSUMER_SECRET','').empty?)
  @base=@env=='production'?'https://api.kra.go.ke':'https://sbx.kra.go.ke';@keys=ENV.fetch('PROXY_API_KEYS','').split(',').map(&:strip).reject(&:empty?);raise 'PROXY_API_KEYS required' if @keys.empty?;@cache={};@hits={};@idempotency={};@service_paths=JSON.parse(ENV.fetch('KRA_SERVICE_PATHS_JSON','{}'));@service_methods=JSON.parse(ENV.fetch('KRA_SERVICE_METHODS_JSON','{}'));@mutex=Mutex.new
 end
 def call(env)
  req=Rack::Request.new(env);path=req.path
  return reply(200,{status:'ok',environment:@env,mock:@mock}) if req.get?&&path=='/health'
  if req.post? && path.start_with?('/v1/kra/')
   key=req.get_header('HTTP_X_API_KEY').to_s;return reply(401,{detail:'Invalid or missing X-API-Key'}) unless @keys.any?{|x|x.bytesize==key.bytesize&&secure_equal(x,key)};return reply(429,{detail:'Rate limit exceeded'}) unless rate(key);return invoke_service(req,path.delete_prefix('/v1/kra/'),key)
  end
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

 def invoke_service(req,id,key)
  mutates=SERVICE_MUTATES[id];return reply(404,{detail:'Unknown KRA service'}) if mutates.nil?
  raw=req.body.read(65_537);return reply(413,{detail:'Request too large'}) if raw.bytesize>65_536
  body=JSON.parse(raw.empty? ? '{}' : raw);return reply(422,{detail:'JSON object required'}) unless body.is_a?(Hash)
  return reply(400,{detail:'consent must be true'}) unless body['consent']==true
  return reply(422,{detail:'payload must be a JSON object'}) unless body['payload'].is_a?(Hash)
  idem=req.get_header('HTTP_IDEMPOTENCY_KEY');return reply(400,{detail:'Idempotency-Key (16-128 chars) is required'}) if mutates&&(idem.nil?||idem.length<16||idem.length>128)
  ik=idem ? Digest::SHA256.hexdigest("#{key}:#{id}:#{idem}") : nil
  fingerprint=Digest::SHA256.hexdigest(JSON.generate(canonicalize(body['payload'])))
  return reply(501,{error:{code:'mock_service_not_implemented',message:'Configure a verified KRA sandbox mapping; no filing or payment mock is fabricated'}}) if @mock
  ck=ENV.fetch('KRA_PIN_CONSUMER_KEY','');cs=ENV.fetch('KRA_PIN_CONSUMER_SECRET','')
  if id=='authorization';token(ck,cs);return reply(200,{authorized:true,token_type:'Bearer'});end
  upstream_path=@service_paths[id];return reply(501,{error:{code:'service_not_configured',message:'No verified KRA endpoint mapping configured'}}) unless upstream_path.is_a?(String)&&upstream_path.start_with?('/')&&!upstream_path.start_with?('//')
  method=(@service_methods[id]||'POST').upcase;return reply(501,{detail:'Unsupported or unsafe configured HTTP method'}) unless ['GET','POST'].include?(method)&&!(method=='GET'&&mutates)
  upstream_base=@base
  begin
   parsed_base=URI(upstream_base);return reply(501,{error:{code:'service_base_not_configured',message:'Set a verified HTTPS KRA base URL for this service'}}) unless parsed_base.scheme=='https'&&parsed_base.host&.end_with?('.kra.go.ke')
   if ik
    prior=@mutex.synchronize do
     existing=@idempotency[ik]
     @idempotency[ik]={fingerprint:fingerprint,state:'pending'} unless existing
     existing
    end
    if prior
     return reply(409,{error:{code:'idempotency_conflict',message:'Idempotency-Key was already used with a different payload'}}) unless prior[:fingerprint]==fingerprint
     return reply(200,prior[:data]) if prior[:state]=='complete'
     return reply(409,{error:{code:'idempotency_in_progress',message:'A request with this Idempotency-Key is already in progress'}}) if prior[:state]=='pending'
     return reply(409,{error:{code:'idempotency_outcome_unknown',message:'Previous request outcome is unknown; reconcile with KRA before retrying'}})
    end
   end
   submitted=false
   begin
    access=token(ck,cs)
    submitted=true
    response=upstream_request(method,upstream_base,upstream_path,body['payload'],access)
    if response.code.to_i==401&&!mutates;@cache.delete(ck);access=token(ck,cs);submitted=true;response=upstream_request(method,upstream_base,upstream_path,body['payload'],access);end
    data=JSON.parse(response.body.empty? ? '{}' : response.body)
    unless response.is_a?(Net::HTTPSuccess)
     if ik
      @mutex.synchronize do
       if response.code.to_i>=500
        @idempotency[ik]={fingerprint:fingerprint,state:'unknown'}
       else
        @idempotency.delete(ik)
       end
      end
     end
     return reply(response.code.to_i==429 ? 429 : 502,{error:{code:'kra_upstream_error',message:'KRA service request failed'}})
    end
    @mutex.synchronize{@idempotency[ik]={fingerprint:fingerprint,state:'complete',data:data}} if ik
    reply(200,data)
   rescue JSON::ParserError
    @mutex.synchronize{@idempotency[ik]={fingerprint:fingerprint,state:'unknown'}} if ik&&submitted
    reply(502,{error:{code:'invalid_upstream_response',message:'KRA returned non-JSON content'}})
   rescue StandardError
    if ik
     @mutex.synchronize do
      if submitted
       @idempotency[ik]={fingerprint:fingerprint,state:'unknown'}
      else
       @idempotency.delete(ik)
      end
     end
    end
    reply(502,{error:{code:'upstream_error',message:'KRA service request failed'}})
   end
  rescue StandardError;reply(502,{error:{code:'upstream_error',message:'KRA service request failed'}})
  end
 end
 def upstream_request(method,base_url,path,payload,access)
  normalized_base=base_url.sub(%r{/+\z},'')
  uri=URI("#{normalized_base}#{path}")
  if method=='GET'
   query=URI.encode_www_form(payload)
   uri.query=[uri.query,query].compact.reject(&:empty?).join('&')
  end
  request=method=='GET' ? Net::HTTP::Get.new(uri) : Net::HTTP::Post.new(uri)
  request['Authorization']="Bearer #{access}";request['Content-Type']='application/json';request.body=JSON.generate(payload) if method=='POST'
  Net::HTTP.start(uri.hostname,uri.port,use_ssl:true,open_timeout:5,read_timeout:20){|http|http.request(request)}
 end

 def canonicalize(value);case value;when Hash;value.keys.sort.each_with_object({}){|key,out|out[key]=canonicalize(value[key])};when Array;value.map{|item|canonicalize(item)};else;value;end;end
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
