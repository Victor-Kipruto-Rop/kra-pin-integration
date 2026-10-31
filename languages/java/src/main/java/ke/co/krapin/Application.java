package ke.co.krapin;
import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.web.bind.annotation.*;import org.springframework.web.client.RestClient;import org.springframework.http.*;import org.springframework.http.client.JdkClientHttpRequestFactory;import java.net.http.HttpClient;import java.time.*;import java.util.*;import java.util.concurrent.*;
@SpringBootApplication @RestController
public class Application {
 final String env=System.getenv().getOrDefault("KRA_ENVIRONMENT","sandbox"),base=env.equals("production")?"https://api.kra.go.ke":"https://sbx.kra.go.ke";
 final boolean mock=Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true")),consent=Boolean.parseBoolean(System.getenv().getOrDefault("REQUIRE_CONSENT","true"));
 static JdkClientHttpRequestFactory requestFactory(){HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();JdkClientHttpRequestFactory f=new JdkClientHttpRequestFactory(client);f.setReadTimeout(Duration.ofSeconds(15));return f;}
 final RestClient http=RestClient.builder().requestFactory(requestFactory()).build();final Map<String,Token> cache=new ConcurrentHashMap<>();final Map<String,ArrayDeque<Instant>> hits=new ConcurrentHashMap<>();
 record Token(String value,Instant expires){} record Body(String pin,String taxpayer_id,String taxpayer_type,Boolean consent){} record Result(boolean found,String pin,String taxpayer_name,String environment,boolean mock,Object raw){}
 public static void main(String[] a){if(System.getenv().getOrDefault("KRA_ENVIRONMENT","sandbox").equals("production")&&Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true")))throw new IllegalStateException("Mock mode forbidden in production");if(System.getenv().getOrDefault("PROXY_API_KEYS","").isBlank())throw new IllegalStateException("PROXY_API_KEYS required");if(!Boolean.parseBoolean(System.getenv().getOrDefault("KRA_MOCK","true"))&&(System.getenv().getOrDefault("KRA_PIN_CONSUMER_KEY","").isBlank()||System.getenv().getOrDefault("KRA_PIN_CONSUMER_SECRET","").isBlank()))throw new IllegalStateException("KRA credentials required when mock mode is disabled");SpringApplication.run(Application.class,a);}
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
 Map<String,Object> err(String c,String m){return Map.of("error",Map.of("code",c,"message",m));}
 String token(String k,String s){Token t=cache.get(k);if(t!=null&&t.expires().isAfter(Instant.now().plusSeconds(60)))return t.value();Map d=http.get().uri(base+"/v1/token/generate?grant_type=client_credentials").headers(h->h.setBasicAuth(k,s)).retrieve().body(Map.class);String v=Objects.toString(d.get("access_token"),"");if(v.isBlank())throw new IllegalStateException("Missing token");cache.put(k,new Token(v,Instant.now().plusSeconds(Long.parseLong(Objects.toString(d.get("expires_in"),"3600")))));return v;}
 boolean authorized(String k){if(k==null)return false;return Arrays.stream(System.getenv().getOrDefault("PROXY_API_KEYS","").split(",")).map(String::trim).filter(x->!x.isEmpty()).anyMatch(x->java.security.MessageDigest.isEqual(x.getBytes(),k.getBytes()));}
 synchronized boolean rate(String k){var q=hits.computeIfAbsent(k,x->new ArrayDeque<>());Instant cut=Instant.now().minusSeconds(60);while(!q.isEmpty()&&q.peek().isBefore(cut))q.poll();if(q.size()>=30)return false;q.add(Instant.now());return true;}
}
