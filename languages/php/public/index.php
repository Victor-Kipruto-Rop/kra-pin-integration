<?php
declare(strict_types=1);
require __DIR__.'/../src/KraService.php';
header('Content-Type: application/json');
$env=getenv('KRA_ENVIRONMENT')?:'sandbox';$mock=(getenv('KRA_MOCK')?:'true')==='true';
if(!in_array($env,['sandbox','production'],true)){http_response_code(500);echo json_encode(['error'=>'KRA_ENVIRONMENT must be sandbox or production']);exit;}
if(!$mock&&(!(getenv('KRA_PIN_CONSUMER_KEY')?:'')||!(getenv('KRA_PIN_CONSUMER_SECRET')?:''))){http_response_code(500);echo json_encode(['error'=>'KRA credentials required when mock mode is disabled']);exit;}
if($mock&&$env==='production'){http_response_code(500);echo json_encode(['error'=>'Mock mode forbidden in production']);exit;}
$keys=array_values(array_filter(array_map('trim',explode(',',getenv('PROXY_API_KEYS')?:''))));if(!$keys){http_response_code(500);echo json_encode(['error'=>'PROXY_API_KEYS required']);exit;}
$path=parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH);
if($path==='/health'&&$_SERVER['REQUEST_METHOD']==='GET'){echo json_encode(['status'=>'ok','environment'=>$env,'mock'=>$mock]);exit;}
$isCatalog=preg_match('#^/v1/kra/([a-z0-9-]+)$#',$path,$catalogMatch)===1;
if($_SERVER['REQUEST_METHOD']!=='POST'||(!in_array($path,['/v1/pin/verify','/v1/pin/verify-by-id'],true)&&!$isCatalog)){http_response_code(404);echo json_encode(['detail'=>'Not found']);exit;}
$key=$_SERVER['HTTP_X_API_KEY']??'';$valid=false;foreach($keys as $candidate){if(hash_equals($candidate,$key))$valid=true;}if(!$valid){http_response_code(401);echo json_encode(['detail'=>'Invalid or missing X-API-Key']);exit;}
$ratePath=sys_get_temp_dir().'/kra-pin-rate-'.hash('sha256',$key);$rateHandle=fopen($ratePath,'c+');if($rateHandle===false){http_response_code(503);echo json_encode(['detail'=>'Rate limiter unavailable']);exit;}flock($rateHandle,LOCK_EX);$rawRate=stream_get_contents($rateHandle);$times=json_decode($rawRate?:'[]',true);if(!is_array($times))$times=[];$now=microtime(true);$times=array_values(array_filter($times,fn($t)=>is_numeric($t)&&$now-(float)$t<60));if(count($times)>=30){flock($rateHandle,LOCK_UN);fclose($rateHandle);http_response_code(429);header('Retry-After: 60');echo json_encode(['detail'=>'Rate limit exceeded']);exit;}$times[]=$now;ftruncate($rateHandle,0);rewind($rateHandle);fwrite($rateHandle,json_encode($times));fflush($rateHandle);flock($rateHandle,LOCK_UN);fclose($rateHandle);

if($isCatalog){
 $mutating=['tax-compliance-certificate-application','nil-return-filing','tot-return-filing','income-tax-withholding-prn-generation','vat-withholding-prn-generation','rental-withholding-prn-generation','etims-oscu-integrator-automated-testing'];
 $serviceId=$catalogMatch[1];
 $all=['authorization','pin-checker-by-pin','pin-checker-by-id','fetch-taxpayer-obligations','know-kra-tax-service-office','tax-compliance-certificate-application','tax-compliance-certificate-checker','vat-exemption-checker','it-exemption-checker','nil-return-filing','tot-return-filing','income-tax-withholding-prn-generation','vat-withholding-prn-generation','rental-withholding-prn-generation','excise-license-checker-by-pin','excise-license-checker-by-certificate-number','customs-declaration-status-checker','customs-tax-calculator','import-certificate-checker-by-pin','import-certificate-checker-by-cert-number','invoice-checker','etims-oscu-integrator-automated-testing'];
 if(!in_array($serviceId,$all,true)){http_response_code(404);echo json_encode(['detail'=>'Unknown KRA service']);exit;}
 $rawBody=file_get_contents('php://input',false,null,0,65537);if(strlen($rawBody)>65536){http_response_code(413);echo json_encode(['detail'=>'Request too large']);exit;}
 $body=json_decode($rawBody?:'{}',true);if(!is_array($body)){http_response_code(422);echo json_encode(['detail'=>'Invalid JSON']);exit;}
 if(($body['consent']??false)!==true){http_response_code(400);echo json_encode(['detail'=>'consent must be true']);exit;}
 if(!isset($body['payload'])||!is_array($body['payload'])){http_response_code(422);echo json_encode(['detail'=>'payload must be a JSON object']);exit;}
 $idem=$_SERVER['HTTP_IDEMPOTENCY_KEY']??'';if(in_array($serviceId,$mutating,true)&&(strlen($idem)<16||strlen($idem)>128)){http_response_code(400);echo json_encode(['detail'=>'Idempotency-Key (16-128 chars) is required']);exit;}
 $idemKey=$idem!==''?hash('sha256',$key.':'.$serviceId.':'.$idem):'';
 if($mock){http_response_code(501);echo json_encode(['error'=>['code'=>'mock_service_not_implemented','message'=>'Configure a verified KRA sandbox mapping; no filing or payment mock is fabricated']]);exit;}
 $idemHandle=null;if($idemKey!==''){$idemFile=sys_get_temp_dir().'/kra-idem-'.$idemKey;$idemHandle=fopen($idemFile,'c+');if($idemHandle===false){http_response_code(503);echo json_encode(['detail'=>'Idempotency store unavailable']);exit;}flock($idemHandle,LOCK_EX);$cachedRaw=stream_get_contents($idemHandle);$cached=$cachedRaw!==''?json_decode($cachedRaw,true):null;if(is_array($cached)) {flock($idemHandle,LOCK_UN);fclose($idemHandle);echo json_encode($cached);exit;}}
 try{$service=new KraPin\KraService($env,false);[$status,$result]=$service->invokeCatalog($serviceId,$body['payload']);if($status===200&&$idemHandle!==null){ftruncate($idemHandle,0);rewind($idemHandle);fwrite($idemHandle,json_encode($result,JSON_THROW_ON_ERROR));fflush($idemHandle);}if($idemHandle!==null){flock($idemHandle,LOCK_UN);fclose($idemHandle);}http_response_code($status);echo json_encode($result,JSON_THROW_ON_ERROR);exit;}
 catch(Throwable $e){if($idemHandle!==null){flock($idemHandle,LOCK_UN);fclose($idemHandle);}http_response_code(502);echo json_encode(['error'=>['code'=>'upstream_error','message'=>'KRA service request failed']]);exit;}
}

$rawBody=file_get_contents('php://input',false,null,0,65537);if(strlen($rawBody)>65536){http_response_code(413);echo json_encode(['detail'=>'Request too large']);exit;}
$body=json_decode($rawBody?:'{}',true);if(!is_array($body)){http_response_code(422);echo json_encode(['detail'=>'Invalid JSON']);exit;}
if((getenv('REQUIRE_CONSENT')?:'true')!=='false'&&($body['consent']??false)!==true){http_response_code(400);echo json_encode(['detail'=>'consent must be true']);exit;}
$byId=$path==='/v1/pin/verify-by-id';$value=strtoupper(trim((string)($byId?($body['taxpayer_id']??''):($body['pin']??''))));
if(strlen($value)<($byId?5:9)||strlen($value)>20||!preg_match('/^[A-Z0-9]+$/',$value)){http_response_code(422);echo json_encode(['detail'=>'Invalid identifier format']);exit;}
try{$service=new KraPin\KraService($env,$mock);echo json_encode($service->verify($byId,$value,strtoupper((string)($body['taxpayer_type']??'KE'))),JSON_THROW_ON_ERROR);}catch(Throwable $e){http_response_code(502);echo json_encode(['error'=>['code'=>'upstream_error','message'=>'KRA request failed']]);}
