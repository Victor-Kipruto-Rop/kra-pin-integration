package main

import (
 "bytes"
 "crypto/sha256"
 "crypto/subtle"
 "encoding/hex"
 "encoding/json"
 "fmt"
 "io"
 "log"
 "net/http"
 "os"
 "strings"
 "sync"
 "time"
)

type Config struct {
 Env, Base, Key, Secret string
 Mock, Consent bool
 APIKeys []string
 Paths, Methods map[string]string
}
type Token struct { Value string; Expires time.Time }
type CachedResponse struct { Status int; Body any }
var tokenCache=struct{sync.Mutex; m map[string]Token}{m:map[string]Token{}}
var idemCache=struct{sync.Mutex; m map[string]CachedResponse}{m:map[string]CachedResponse{}}
var serviceMutates=map[string]bool{
 "authorization":false,"pin-checker-by-pin":false,"pin-checker-by-id":false,
 "fetch-taxpayer-obligations":false,"know-kra-tax-service-office":false,
 "tax-compliance-certificate-application":true,"tax-compliance-certificate-checker":false,
 "vat-exemption-checker":false,"it-exemption-checker":false,"nil-return-filing":true,
 "tot-return-filing":true,"income-tax-withholding-prn-generation":true,
 "vat-withholding-prn-generation":true,"rental-withholding-prn-generation":true,
 "excise-license-checker-by-pin":false,"excise-license-checker-by-certificate-number":false,
 "customs-declaration-status-checker":false,"customs-tax-calculator":false,
 "import-certificate-checker-by-pin":false,"import-certificate-checker-by-cert-number":false,
 "invoice-checker":false,"etims-oscu-integrator-automated-testing":true,
}
func env(k,d string) string { if v:=os.Getenv(k);v!="" { return v }; return d }
func loadConfig() Config {
 e:=env("KRA_ENVIRONMENT","sandbox")
 if e!="sandbox"&&e!="production" { log.Fatal("KRA_ENVIRONMENT must be sandbox or production") }
 base:="https://sbx.kra.go.ke"; if e=="production" { base="https://api.kra.go.ke" }
 c:=Config{Env:e,Base:base,Key:os.Getenv("KRA_PIN_CONSUMER_KEY"),Secret:os.Getenv("KRA_PIN_CONSUMER_SECRET"),Mock:env("KRA_MOCK","true")=="true",Consent:env("REQUIRE_CONSENT","true")!="false",APIKeys:strings.Split(os.Getenv("PROXY_API_KEYS"),",")}
 if c.Mock&&e=="production" { log.Fatal("mock mode forbidden in production") }
 if !c.Mock&&(c.Key==""||c.Secret=="") { log.Fatal("KRA credentials required when mock mode is disabled") }
 valid:=false;for _,k:=range c.APIKeys { if strings.TrimSpace(k)!="" { valid=true } };if !valid { log.Fatal("PROXY_API_KEYS required") }
 if err:=json.Unmarshal([]byte(env("KRA_SERVICE_PATHS_JSON","{}")),&c.Paths);err!=nil { log.Fatal("invalid KRA_SERVICE_PATHS_JSON") }
 if err:=json.Unmarshal([]byte(env("KRA_SERVICE_METHODS_JSON","{}")),&c.Methods);err!=nil { log.Fatal("invalid KRA_SERVICE_METHODS_JSON") }
 return c
}
func write(w http.ResponseWriter,status int,v any) { w.Header().Set("Content-Type","application/json");w.WriteHeader(status);_ = json.NewEncoder(w).Encode(v) }
func authorized(c Config,key string) bool { if key=="" { return false };for _,candidate:=range c.APIKeys { candidate=strings.TrimSpace(candidate);if len(candidate)==len(key)&&subtle.ConstantTimeCompare([]byte(candidate),[]byte(key))==1{return true} };return false }
func callerID(key string) string { sum:=sha256.Sum256([]byte(key));return hex.EncodeToString(sum[:8]) }
type Limiter struct { mu sync.Mutex; hits map[string][]time.Time }
func (l *Limiter) allow(key string) bool { l.mu.Lock();defer l.mu.Unlock();now:=time.Now();q:=[]time.Time{};for _,t:=range l.hits[key]{if now.Sub(t)<time.Minute{q=append(q,t)}};if len(q)>=30{return false};l.hits[key]=append(q,now);return true }
func getToken(c Config,client *http.Client)(string,error) {
 tokenCache.Lock();defer tokenCache.Unlock()
 if t,ok:=tokenCache.m[c.Key];ok&&t.Expires.After(time.Now().Add(time.Minute)){return t.Value,nil}
 req,err:=http.NewRequest("GET",c.Base+"/v1/token/generate?grant_type=client_credentials",nil);if err!=nil{return "",err};req.SetBasicAuth(c.Key,c.Secret)
 resp,err:=client.Do(req);if err!=nil{return "",err};defer resp.Body.Close()
 var data map[string]any;if err=json.NewDecoder(io.LimitReader(resp.Body,1<<20)).Decode(&data);err!=nil{return "",err}
 value,_:=data["access_token"].(string);if resp.StatusCode>=400||value==""{return "",fmt.Errorf("KRA authorization failed")}
 ttl:=3600*time.Second;if n,ok:=data["expires_in"].(float64);ok&&n>0{ttl=time.Duration(n)*time.Second}
 tokenCache.m[c.Key]=Token{value,time.Now().Add(ttl)};return value,nil
}
func invoke(c Config,client *http.Client,service string,payload map[string]any)(int,any,error) {
 if service=="authorization" { tok,err:=getToken(c,client);if err!=nil{return 0,nil,err};return 200,map[string]any{"access_token":tok,"token_type":"Bearer"},nil }
 path:=c.Paths[service];if path==""||!strings.HasPrefix(path,"/")||strings.HasPrefix(path,"//"){return 501,map[string]any{"error":map[string]string{"code":"service_not_configured","message":"No verified KRA endpoint mapping configured"}},nil}
 method:=strings.ToUpper(c.Methods[service]);if method==""{method="POST"};if method!="GET"&&method!="POST"{return 500,nil,fmt.Errorf("unsupported configured HTTP method")}
 tok,err:=getToken(c,client);if err!=nil{return 0,nil,err}
 send:=func(token string)(*http.Response,error){var body io.Reader;if method=="POST"{b,e:=json.Marshal(payload);if e!=nil{return nil,e};body=bytes.NewReader(b)};req,e:=http.NewRequest(method,c.Base+path,body);if e!=nil{return nil,e};req.Header.Set("Authorization","Bearer "+token);if method=="POST"{req.Header.Set("Content-Type","application/json")};return client.Do(req)}
 resp,err:=send(tok);if err!=nil{return 0,nil,err};if resp.StatusCode==401{resp.Body.Close();tokenCache.Lock();delete(tokenCache.m,c.Key);tokenCache.Unlock();tok,err=getToken(c,client);if err!=nil{return 0,nil,err};resp,err=send(tok);if err!=nil{return 0,nil,err}}
 defer resp.Body.Close();raw,err:=io.ReadAll(io.LimitReader(resp.Body,2<<20));if err!=nil{return 0,nil,err};var result any;if len(raw)>0{if err=json.Unmarshal(raw,&result);err!=nil{return 502,map[string]string{"code":"invalid_upstream_response","message":"KRA returned non-JSON content"},nil}}
 if resp.StatusCode==429{return 429,result,nil};if resp.StatusCode>=400{return 502,map[string]any{"error":map[string]any{"code":"kra_upstream_error","message":"KRA service request failed","upstream_status":resp.StatusCode}},nil};return 200,result,nil
}
func serviceHandler(c Config,client *http.Client,limiter *Limiter) http.HandlerFunc {
 return func(w http.ResponseWriter,r *http.Request){
  key:=r.Header.Get("X-API-Key");if !authorized(c,key){write(w,401,map[string]string{"detail":"Invalid or missing X-API-Key"});return};if !limiter.allow(callerID(key)){write(w,429,map[string]string{"detail":"Rate limit exceeded"});return}
  service:=strings.TrimPrefix(r.URL.Path,"/v1/kra/");mutates,ok:=serviceMutates[service];if !ok{write(w,404,map[string]string{"detail":"Unknown KRA service"});return}
  bodyBytes,err:=io.ReadAll(http.MaxBytesReader(w,r.Body,65536));if err!=nil{write(w,413,map[string]string{"detail":"Request too large"});return}
  var body struct{Consent bool `json:"consent"`;Payload map[string]any `json:"payload"`};if json.Unmarshal(bodyBytes,&body)!=nil{write(w,422,map[string]string{"detail":"Invalid JSON"});return}
  if c.Consent&&!body.Consent{write(w,400,map[string]string{"detail":"consent must be true"});return};if body.Payload==nil{write(w,422,map[string]string{"detail":"payload must be a JSON object"});return}
  idem:=r.Header.Get("Idempotency-Key");if mutates&&(len(idem)<16||len(idem)>128){write(w,400,map[string]string{"detail":"Idempotency-Key (16-128 chars) is required"});return}
  idemKey:="";if idem!=""{sum:=sha256.Sum256([]byte(key+":"+service+":"+idem));idemKey=hex.EncodeToString(sum[:]);idemCache.Lock();cached,exists:=idemCache.m[idemKey];idemCache.Unlock();if exists{write(w,cached.Status,cached.Body);return}}
  if c.Mock{write(w,501,map[string]string{"code":"mock_service_not_implemented","message":"No fabricated mock response; configure verified KRA sandbox mapping"});return}
  status,data,err:=invoke(c,client,service,body.Payload);if err!=nil{write(w,502,map[string]string{"code":"upstream_error","message":"KRA service request failed"});return}
  if idemKey!=""&&status==200{idemCache.Lock();idemCache.m[idemKey]=CachedResponse{status,data};idemCache.Unlock()};write(w,status,data)
 }
}
func main(){
 c:=loadConfig();client:=&http.Client{Timeout:20*time.Second};limiter:=&Limiter{hits:map[string][]time.Time{}};mux:=http.NewServeMux()
 mux.HandleFunc("GET /health",func(w http.ResponseWriter,r *http.Request){write(w,200,map[string]any{"status":"ok","environment":c.Env,"mock":c.Mock,"services":len(serviceMutates)})})
 mux.HandleFunc("POST /v1/kra/",serviceHandler(c,client,limiter))
 srv:=&http.Server{Addr:":"+env("PORT","8000"),Handler:mux,ReadHeaderTimeout:5*time.Second,ReadTimeout:20*time.Second,WriteTimeout:25*time.Second,IdleTimeout:60*time.Second}
 log.Fatal(srv.ListenAndServe())
}
