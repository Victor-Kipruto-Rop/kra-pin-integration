import http from 'node:http';import {createHash,timingSafeEqual} from 'node:crypto';import {pathToFileURL} from 'node:url';
const env=process.env.KRA_ENVIRONMENT||'sandbox',mock=(process.env.KRA_MOCK||'true')==='true',base=env==='production'?'https://api.kra.go.ke':'https://sbx.kra.go.ke',keys=(process.env.PROXY_API_KEYS||'').split(',').map(x=>x.trim()).filter(Boolean),consent=(process.env.REQUIRE_CONSENT||'true')!=='false',cache=new Map(),hits=new Map(),idempotency=new Map();
if(!['sandbox','production'].includes(env))throw Error('KRA_ENVIRONMENT must be sandbox or production');if(mock&&env==='production')throw Error('Mock mode forbidden in production');if(!mock&&(!process.env.KRA_PIN_CONSUMER_KEY||!process.env.KRA_PIN_CONSUMER_SECRET))throw Error('KRA credentials required when mock mode is disabled');if(!keys.length)throw Error('PROXY_API_KEYS required');
export const services={
'authorization':false,'pin-checker-by-pin':false,'pin-checker-by-id':false,'fetch-taxpayer-obligations':false,'know-kra-tax-service-office':false,'tax-compliance-certificate-application':true,'tax-compliance-certificate-checker':false,'vat-exemption-checker':false,'it-exemption-checker':false,'nil-return-filing':true,'tot-return-filing':true,'income-tax-withholding-prn-generation':true,'vat-withholding-prn-generation':true,'rental-withholding-prn-generation':true,'excise-license-checker-by-pin':false,'excise-license-checker-by-certificate-number':false,'customs-declaration-status-checker':false,'customs-tax-calculator':false,'import-certificate-checker-by-pin':false,'import-certificate-checker-by-cert-number':false,'invoice-checker':false,'etims-oscu-integrator-automated-testing':true};
const servicePaths=JSON.parse(process.env.KRA_SERVICE_PATHS_JSON||'{}'),serviceMethods=JSON.parse(process.env.KRA_SERVICE_METHODS_JSON||'{}');
const etimsBase=process.env.KRA_ETIMS_BASE_URL||'';

function buildServiceUrl(base,path,payload,method){const u=new URL(base.replace(/\/+$/,'')+path);if(method==='GET')for(const [key,value] of Object.entries(payload)){if(value!==null&&typeof value==='object')throw Error('GET query parameters must be scalar');if(value!==null)u.searchParams.set(key,String(value));}return u.toString();}
function stableJson(value){if(Array.isArray(value))return '['+value.map(stableJson).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stableJson(value[k])).join(',')+'}';return JSON.stringify(value);}
const send=(r,s,d)=>{r.writeHead(s,{'content-type':'application/json'});r.end(JSON.stringify(d));};
const auth=k=>!!k&&keys.some(v=>Buffer.byteLength(v)===Buffer.byteLength(k)&&timingSafeEqual(Buffer.from(v),Buffer.from(k)));
function rate(k){let q=(hits.get(k)||[]).filter(t=>Date.now()-t<60000);if(q.length>=30)return false;q.push(Date.now());hits.set(k,q);return true;}
async function read(req){const chunks=[];let size=0;for await(const c of req){size+=c.length;if(size>65536)throw Object.assign(Error('Request too large'),{status:413});chunks.push(c);}const value=JSON.parse(Buffer.concat(chunks).toString('utf8')||'{}');if(!value||typeof value!=='object'||Array.isArray(value))throw Error('JSON object required');return value;}
async function token(k,s){let t=cache.get(k);if(t&&t.exp>Date.now()+60000)return t.value;let r=await fetch(base+'/v1/token/generate?grant_type=client_credentials',{headers:{authorization:'Basic '+Buffer.from(k+':'+s).toString('base64')},signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('KRA token endpoint rejected credentials');let d=await r.json();if(!d.access_token)throw Error('Malformed token response');cache.set(k,{value:d.access_token,exp:Date.now()+Number(d.expires_in||3600)*1000});return d.access_token;}
export async function lookup(byId,v,type='KE'){if(mock){let found=byId?v==='00000000':v==='A000000000B';return {found,pin:found?'A000000000B':null,taxpayer_name:found?'DEMO T*****':null,environment:env,mock:true,raw:null};}
 let k=process.env[byId?'KRA_PIN_BY_ID_CONSUMER_KEY':'KRA_PIN_CONSUMER_KEY']||process.env.KRA_PIN_CONSUMER_KEY,s=process.env[byId?'KRA_PIN_BY_ID_CONSUMER_SECRET':'KRA_PIN_CONSUMER_SECRET']||process.env.KRA_PIN_CONSUMER_SECRET,t=await token(k,s),path=byId?'/checker/v1/pin':'/checker/v1/pinbypin',payload=byId?{TaxpayerType:type,TaxpayerID:v}:{KRAPIN:v},r=await fetch(base+path,{method:'POST',headers:{authorization:'Bearer '+t,'content-type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)}),d=await r.json();
 if(r.status===404||String(d.errorCode)==='30002')return {found:false,pin:null,taxpayer_name:null,environment:env,mock:false,raw:null};let x=d.PINDATA||d,pin=x.KRAPIN||null,name=x.Name||null;if(!r.ok||(!pin&&!name))throw Error('Unexpected KRA response shape');return {found:true,pin,taxpayer_name:name,environment:env,mock:false,raw:null};}
async function invokeService(req,res,id,k){
 if(!Object.hasOwn(services,id))return send(res,404,{detail:'Unknown KRA service'});
 let body;try{body=await read(req);}catch(e){return send(res,e?.status||422,{detail:e instanceof SyntaxError?'Invalid JSON':'Invalid request body'});}
 if(body.consent!==true)return send(res,400,{detail:'consent must be true'});
 if(!body.payload||typeof body.payload!=='object'||Array.isArray(body.payload))return send(res,422,{detail:'payload must be a JSON object'});
 const idem=req.headers['idempotency-key'];
 if(services[id]&&(!idem||idem.length<16||idem.length>128))return send(res,400,{detail:'Idempotency-Key (16-128 chars) is required for this operation'});
 const idemKey=idem?createHash('sha256').update(k+':'+id+':'+idem).digest('hex'):null;
 const fingerprint=createHash('sha256').update(stableJson(body.payload)).digest('hex');
 if(idemKey&&idempotency.has(idemKey)){
  const prior=idempotency.get(idemKey);
  if(prior.fingerprint!==fingerprint)return send(res,409,{error:{code:'idempotency_conflict',message:'Idempotency-Key was already used with a different payload'}});
  if(prior.state==='unknown')return send(res,409,{error:{code:'idempotency_outcome_unknown',message:'Previous request outcome is unknown; reconcile with KRA before retrying'}});
  if(prior.state==='pending')return send(res,409,{error:{code:'idempotency_in_progress',message:'A request with this Idempotency-Key is already in progress'}});
  if(prior.state==='complete')return send(res,200,prior.data);
 }
 if(mock)return send(res,501,{error:{code:'mock_service_not_implemented',message:'This service has no fabricated mock response; configure a verified KRA sandbox mapping'}});
 const ck=process.env.KRA_PIN_CONSUMER_KEY,cs=process.env.KRA_PIN_CONSUMER_SECRET;
 if(id==='authorization'){try{await token(ck,cs);return send(res,200,{authorized:true,token_type:'Bearer'});}catch{return send(res,502,{error:{code:'authorization_failed',message:'KRA authorization failed'}});}}
 const path=servicePaths[id];if(typeof path!=='string'||!path.startsWith('/')||path.startsWith('//'))return send(res,501,{error:{code:'service_not_configured',message:'No verified KRA endpoint mapping configured for this service'}});
 const method=String(serviceMethods[id]||'POST').toUpperCase();if(!['GET','POST'].includes(method)||(method==='GET'&&services[id]))return send(res,501,{detail:'Unsupported or unsafe configured HTTP method'});
 const upstreamBase=base;try{const u=new URL(upstreamBase);if(u.protocol!=='https:'||!u.hostname.endsWith('.kra.go.ke'))throw Error('invalid host');}catch{return send(res,501,{error:{code:'service_base_not_configured',message:'Set a verified HTTPS KRA base URL for this service'}});}
 let target;try{target=buildServiceUrl(upstreamBase,path,body.payload,method);}catch{return send(res,422,{detail:'GET query payload values must be scalar'});}
 if(idemKey)idempotency.set(idemKey,{fingerprint,state:'pending'});
 let submitted=false;
 try{
  let tok=await token(ck,cs);
  submitted=true;
  let response=await fetch(target,{method,headers:{authorization:'Bearer '+tok,'content-type':'application/json'},...(method==='POST'?{body:JSON.stringify(body.payload)}:{}),signal:AbortSignal.timeout(20000)});
  if(response.status===401&&!services[id]){cache.delete(ck);tok=await token(ck,cs);submitted=true;response=await fetch(target,{method,headers:{authorization:'Bearer '+tok,'content-type':'application/json'},...(method==='POST'?{body:JSON.stringify(body.payload)}:{}),signal:AbortSignal.timeout(20000)});}
  const raw=await response.text();let data;try{data=raw?JSON.parse(raw):{};}catch{
   if(idemKey)idempotency.set(idemKey,{fingerprint,state:'unknown'});
   return send(res,502,{error:{code:'invalid_upstream_response',message:'KRA returned non-JSON content'}});
  }
  if(!response.ok){
   if(idemKey){if(response.status>=500)idempotency.set(idemKey,{fingerprint,state:'unknown'});else idempotency.delete(idemKey);}
   return send(res,response.status===429?429:502,{error:{code:'kra_upstream_error',message:'KRA service request failed',upstream_status:response.status}});
  }
  if(idemKey)idempotency.set(idemKey,{fingerprint,state:'complete',data});
  return send(res,200,data);
 }catch{
  if(idemKey){if(submitted)idempotency.set(idemKey,{fingerprint,state:'unknown'});else idempotency.delete(idemKey);}
  return send(res,502,{error:{code:'upstream_error',message:'KRA service request failed'}});
 }
}

export const server=http.createServer(async(req,res)=>{if(req.method==='GET'&&req.url==='/health')return send(res,200,{status:'ok',environment:env,mock,services:Object.keys(services).length});let k=req.headers['x-api-key'];if(req.method==='POST'&&req.url?.startsWith('/v1/kra/')){if(!auth(k))return send(res,401,{detail:'Invalid or missing X-API-Key'});let caller=createHash('sha256').update(k).digest('hex').slice(0,16);if(!rate(caller))return send(res,429,{detail:'Rate limit exceeded'});return invokeService(req,res,decodeURIComponent(req.url.slice('/v1/kra/'.length)),k);}if(req.method!=='POST'||!['/v1/pin/verify','/v1/pin/verify-by-id'].includes(req.url))return send(res,404,{detail:'Not found'});if(!auth(k))return send(res,401,{detail:'Invalid or missing X-API-Key'});let id=createHash('sha256').update(k).digest('hex').slice(0,16);if(!rate(id))return send(res,429,{detail:'Rate limit exceeded'});try{let b=await read(req),byId=req.url.endsWith('verify-by-id');if(consent&&b.consent!==true)return send(res,400,{detail:'consent must be true'});let v=String(byId?b.taxpayer_id||'':b.pin||'').trim().toUpperCase();if(v.length<(byId?5:9)||v.length>20||!/^[A-Z0-9]+$/.test(v))return send(res,422,{detail:'Invalid identifier format'});return send(res,200,await lookup(byId,v,String(b.taxpayer_type||'KE').toUpperCase()));}catch(e){if(e?.status===413)return send(res,413,{detail:'Request too large'});if(e instanceof SyntaxError)return send(res,422,{detail:'Invalid JSON'});return send(res,502,{error:{code:'upstream_error',message:'KRA request failed'}});}});
server.requestTimeout=20000;server.headersTimeout=10000;server.maxHeadersCount=50;
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href)server.listen(Number(process.env.PORT||8000),()=>console.log('KRA PIN JS listening'));
