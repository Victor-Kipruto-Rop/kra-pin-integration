package ke.co.krapin;
import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.client.RestClient;import org.springframework.http.*;import com.fasterxml.jackson.core.type.TypeReference;import com.fasterxml.jackson.databind.ObjectMapper;import org.springframework.http.client.JdkClientHttpRequestFactory;import org.springframework.web.util.UriComponentsBuilder;import java.net.http.HttpClient;import java.net.URI;import java.time.*;import java.util.*;import java.util.concurrent.*;
@SpringBootApplication @RestController
public class Application {
 final String env=System.getenv().getOrDefault("KRA_ENVIRONMENT","sandbox"),base=env.equals("production")?"https://api.kra.go.ke":"https://sbx.kra.go.ke";
 final boolean mock=Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true")),consent=Boolean.parseBoolean(System.getenv().getOrDefault("REQUIRE_CONSENT","true"));
 static JdkClientHttpRequestFactory requestFactory(){HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();JdkClientHttpRequestFactory f=new JdkClientHttpRequestFactory(client);f.setReadTimeout(Duration.ofSeconds(15));return f;}
 final RestClient http=RestClient.builder().requestFactory(requestFactory()).build();final Map<String,Token> cache=new ConcurrentHashMap<>();final Map<String,ArrayDeque<Instant>> hits=new ConcurrentHashMap<>();final Map<String,Object> idempotency=new ConcurrentHashMap<>();final ObjectMapper mapper=new ObjectMapper();
 record Token(String value,Instant expires){} record Body(String pin,String taxpayer_id,String taxpayer_type,Boolean consent){} record Result(boolean found,String pin,String taxpayer_name,String environment,boolean mock,Object raw){}
 public static void main(String[] a){String environment=System.getenv().getOrDefault("KRA_ENVIRONMENT","sandbox");if(!environment.equals("sandbox")&&!environment.equals("production"))throw new IllegalStateException("KRA_ENVIRONMENT must be sandbox or production");if(environment.equals("production")&&Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true")))throw new IllegalStateException("Mock mode forbidden in production");if(System.getenv().getOrDefault("PROXY_API_KEYS","").isBlank())throw new IllegalStateException("PROXY_API_KEYS required");if(!Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true"))&&(System.getenv().getOrDefault("KRA_PIN_CONSUMER_KEY","").isBlank()||System.getenv().getOrDefault("KRA_PIN_CONSUMER_SECRET","").isBlank()))throw new IllegalStateException("KRA credentials required when mock mode is disabled");SpringApplication.run(Application.class,a);}

 static final Map<String,Boolean> SERVICES=Map.ofEntries(
 Map.entry("authorization",false),Map.entry("pin-checker-by-pin",false),Map.entry("pin-checker-by-id",false),Map.entry("fetch-taxpayer-obligations",false),Map.entry("know-kra-tax-service-office",false),Map.entry("tax-compliance-certificate-application",true),Map.entry("tax-compliance-certificate-checker",false),Map.entry("vat-exemption-checker",false),Map.entry("it-exemption-checker",false),Map.entry("nil-return-filing",true),Map.entry("tot-return-filing",true),Map.entry("income-tax-withholding-prn-generation",true),Map.entry("vat-withholding-prn-generation",true),Map.entry("rental-withholding-prn-generation",true),Map.entry("excise-license-checker-by-pin",false),Map.entry("excise-license-checker-by-certificate-number",false),Map.entry("customs-declaration-status-checker",false),Map.entry("customs-tax-calculator",false),Map.entry("import-certificate-checker-by-pin",false),Map.entry("import-certificate-checker-by-cert-number",false),Map.entry("invoice-checker",false),Map.entry("etims-oscu-integrator-automated-testing",true));
 @PostMapping("/v1/kra/{service}") ResponseEntity<?> invoke(@PathVariable String service,@RequestHeader(value="X-API-Key",required=false)String key,@RequestHeader(value="Idempotency-Key",required=false)String idem,@RequestBody Map<String,Object> body){
  if(!authorized(key))return ResponseEntity.status(401).body(Map.of("detail","Invalid or missing X-API-Key"));if(!rate(key))return ResponseEntity.status(429).body(Map.of("detail","Rate limit exceeded"));
  if(!SERVICES.containsKey(service))return ResponseEntity.status(404).body(Map.of("detail","Unknown KRA service"));if(!Boolean.TRUE.equals(body.get("consent")))return ResponseEntity.badRequest().body(Map.of("detail","consent must be true"));
  if(!(body.get("payload") instanceof Map))return ResponseEntity.unprocessableEntity().body(Map.of("detail","payload must be a JSON object"));
  if(SERVICES.get(service)&&(idem==null||idem.length()<16||idem.length()>128))return ResponseEntity.badRequest().body(Map.of("detail","Idempotency-Key (16-128 chars) is required"));
  String ik=idem==null?null:idemDigest(key+":"+service+":"+idem);String fingerprint;try{fingerprint=idem==null?null:idemDigest(mapper.writer().with(com.fasterxml.jackson.databind.SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS).writeValueAsString(body.get("payload")));}catch(Exception ex){return ResponseEntity.unprocessableEntity().body(Map.of("detail","payload cannot be canonicalized"));}if(ik!=null&&idempotency.containsKey(ik)){Map prior=(Map)idempotency.get(ik);if(!Objects.equals(prior.get("fingerprint"),fingerprint))return ResponseEntity.status(409).body(err("idempotency_conflict","Idempotency-Key was already used with a different payload"));return ResponseEntity.ok(prior.get("data"));}
  if(mock)return ResponseEntity.status(501).body(Map.of("error",Map.of("code","mock_service_not_implemented","message","Configure verified KRA sandbox mappings; no filing or payment mock is fabricated")));
  String ck=System.getenv().getOrDefault("KRA_PIN_CONSUMER_KEY",""),cs=System.getenv().getOrDefault("KRA_PIN_CONSUMER_SECRET","");
  if(service.equals("authorization")){try{token(ck,cs);return ResponseEntity.ok(Map.of("authorized",true,"token_type","Bearer"));}catch(Exception e){return ResponseEntity.status(502).body(err("authorization_failed","KRA authorization failed"));}}
  try{
   Map<String,String> paths=mapper.readValue(System.getenv().getOrDefault("KRA_SERVICE_PATHS_JSON","{}"),new TypeReference<>(){});
   String path=paths.get(service);if(path==null||!path.startsWith("/")||path.startsWith("//"))return ResponseEntity.status(501).body(Map.of("error",Map.of("code","service_not_configured","message","No verified KRA endpoint mapping configured")));
   Map<String,String> methods=mapper.readValue(System.getenv().getOrDefault("KRA_SERVICE_METHODS_JSON","{}"),new TypeReference<>(){});String method=methods.getOrDefault(service,"POST").toUpperCase();if((!method.equals("POST")&&!method.equals("GET"))||(method.equals("GET")&&SERVICES.get(service)))return ResponseEntity.status(501).body(Map.of("detail","Unsupported or unsafe configured HTTP method"));
   String upstreamBase=base;try{URI u=URI.create(upstreamBase);if(!"https".equals(u.getScheme())||u.getHost()==null||!u.getHost().endsWith(".kra.go.ke"))return ResponseEntity.status(501).body(Map.of("error",Map.of("code","service_base_not_configured","message","Set a verified HTTPS KRA base URL for this service")));}catch(Exception ex){return ResponseEntity.status(501).body(Map.of("error",Map.of("code","service_base_not_configured","message","Set a verified HTTPS KRA base URL for this service")));}String tok=token(ck,cs);Object payload=body.get("payload");URI target;try{target=targetUri(upstreamBase,path,payload,method);}catch(IllegalArgumentException ex){return ResponseEntity.unprocessableEntity().body(Map.of("detail","GET query payload values must be scalar"));}Map result;
   try{result=method.equals("POST")?http.post().uri(target).header("Authorization","Bearer "+tok).body(payload).retrieve().body(Map.class):http.get().uri(target).header("Authorization","Bearer "+tok).retrieve().body(Map.class);}
   catch(org.springframework.web.client.HttpClientErrorException.Unauthorized ex){cache.remove(ck);tok=token(ck,cs);result=method.equals("POST")?http.post().uri(target).header("Authorization","Bearer "+tok).body(payload).retrieve().body(Map.class):http.get().uri(target).header("Authorization","Bearer "+tok).retrieve().body(Map.class);}
   if(result==null)result=Map.of();if(ik!=null)idempotency.put(ik,Map.of("fingerprint",fingerprint,"data",result));return ResponseEntity.ok(result);
  }catch(org.springframework.web.client.RestClientResponseException e){return ResponseEntity.status(e.getStatusCode().value()==429?429:502).body(err("kra_upstream_error","KRA service request failed"));}
  catch(Exception e){return ResponseEntity.status(502).body(err("upstream_error","KRA service request failed"));}
 }

 @GetMapping("/health") Map<String,Object> health(){return Map.of("status","ok","environment",env,"mock",mock);}
 @PostMapping("/v1/pin/verify") ResponseEntity<?> pin(@RequestHeader(value="X-API-Key",required=false)String k,@RequestBody Body b){return verify(k,b,false);}
 @PostMapping("/v1/pin/verify-by-id") ResponseEntity<?> byId(@RequestHeader(value="X-API-Key",required=false)String k,@RequestBody Body b){return verify(k,b,true);}
 ResponseEntity<?> verify(String k,Body b,boolean id){
  if(!authorized(k))return ResponseEntity.status(401).body(Map.of("detail","Invalid or missing X-API-Key"));if(!rate(k))return ResponseEntity.status(429).body(Map.of("detail","Rate limit exceeded"));
  if(consent&&!Boolean.TRUE.equals(b.consent()))return ResponseEntity.badRequest().body(Map.of("detail","consent must be true"));
  String value=id?b.taxpayer_id():b.pin();if(value==null||value.length()<(id?5:9)||value.length()>20||!value.matches("[A-Za-z0-9]+"))return ResponseEntity.unprocessableEntity().body(Map.of("detail","Invalid identifier format"));
  if(mock){boolean found=id?value.equals("00000000"):value.equals("A000000000B");return ResponseEntity.ok(new Result(found,found?"A000000000B":null,found?"DEMO T*****":null,env,true,null));}
  try{String key=System.getenv().getOrDefault(id?"KRA_PIN_BY_ID_CONSUMER_KEY":"KRA_PIN_CONSUMER_KEY",System.getenv().getOrDefault("KRA_PIN_CONSUMER_KEY",""));String secret=System.getenv().getOrDefault(id?"KRA_PIN_BY_ID_CONSUMER_SECRET":"KRA_PIN_CONSUMER_SECRET",System.getenv().getOrDefault("KRA_PIN_CONSUMER_SECRET",""));String tok=token(key,secret);
   Map<String,String> payload=id?Map.of("TaxpayerType",Objects.toString(b.taxpayer_type(),"KE"),"TaxpayerID",value):Map.of("KRAPIN",value);String path=id?"/checker/v1/pin":"/checker/v1/pinbypin";
   Map d=http.post().uri(base+path).header("Authorization","Bearer "+tok).body(payload).retrieve().body(Map.class);Map rec=d.get("PINDATA") instanceof Map?(Map)d.get("PINDATA"):d;String pin=Objects.toString(rec.get("KRAPIN"),null),name=Objects.toString(rec.get("Name"),null);
   if(pin==null&&name==null)return ResponseEntity.status(502).body(err("unexpected_response","Unexpected KRA response"));return ResponseEntity.ok(new Result(true,pin,name,env,false,null));
  }catch(Exception e){return ResponseEntity.status(502).body(err("upstream_error","KRA request failed; details withheld"));}
 }
 URI targetUri(String upstreamBase,String path,Object payload,String method){
  String normalized=upstreamBase.replaceAll("/+$","")+path;
  var builder=UriComponentsBuilder.fromUriString(normalized);
  if(method.equals("GET")&&payload instanceof Map<?,?> values){
   for(var entry:values.entrySet()){
    Object value=entry.getValue();
    if(value instanceof Map<?,?>||value instanceof Collection<?>)throw new IllegalArgumentException("GET query payload values must be scalar");
    if(value!=null)builder.queryParam(Objects.toString(entry.getKey()),value);
   }
  }
  return builder.build().encode().toUri();
 }
 String idemDigest(String value){try{return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}
 Map<String,Object> err(String c,String m){return Map.of("error",Map.of("code",c,"message",m));}
 String token(String k,String s){Token t=cache.get(k);if(t!=null&&t.expires().isAfter(Instant.now().plusSeconds(60)))return t.value();Map d=http.get().uri(base+"/v1/token/generate?grant_type=client_credentials").headers(h->h.setBasicAuth(k,s)).retrieve().body(Map.class);String v=Objects.toString(d.get("access_token"),"");if(v.isBlank())throw new IllegalStateException("Missing token");cache.put(k,new Token(v,Instant.now().plusSeconds(Long.parseLong(Objects.toString(d.get("expires_in"),"3600")))));return v;}
 boolean authorized(String k){if(k==null)return false;return Arrays.stream(System.getenv().getOrDefault("PROXY_API_KEYS","").split(",")).map(String::trim).filter(x->!x.isEmpty()).anyMatch(x->java.security.MessageDigest.isEqual(x.getBytes(),k.getBytes()));}
 synchronized boolean rate(String k){var q=hits.computeIfAbsent(k,x->new ArrayDeque<>());Instant cut=Instant.now().minusSeconds(60);while(!q.isEmpty()&&q.peek().isBefore(cut))q.poll();if(q.size()>=30)return false;q.add(Instant.now());return true;}
}
