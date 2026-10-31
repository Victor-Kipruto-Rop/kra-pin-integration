<?php
declare(strict_types=1);
require __DIR__.'/../src/KraService.php';
header('Content-Type: application/json');
$env=getenv('KRA_ENVIRONMENT')?:'sandbox';$mock=(getenv('KRA_MOCK')?:'true')==='true';
if($mock&&$env==='production'){http_response_code(500);echo json_encode(['error'=>'Mock mode forbidden in production']);exit;}
$keys=array_values(array_filter(array_map('trim',explode(',',getenv('PROXY_API_KEYS')?:''))));if(!$keys){http_response_code(500);echo json_encode(['error'=>'PROXY_API_KEYS required']);exit;}
$path=parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH);
if($path==='/health'&&$_SERVER['REQUEST_METHOD']==='GET'){echo json_encode(['status'=>'ok','environment'=>$env,'mock'=>$mock]);exit;}
if($_SERVER['REQUEST_METHOD']!=='POST'||!in_array($path,['/v1/pin/verify','/v1/pin/verify-by-id'],true)){http_response_code(404);echo json_encode(['detail'=>'Not found']);exit;}
$key=$_SERVER['HTTP_X_API_KEY']??'';$valid=false;foreach($keys as $candidate){if(hash_equals($candidate,$key))$valid=true;}if(!$valid){http_response_code(401);echo json_encode(['detail'=>'Invalid or missing X-API-Key']);exit;}
$body=json_decode(file_get_contents('php://input')?:'{}',true);if(!is_array($body)){http_response_code(422);echo json_encode(['detail'=>'Invalid JSON']);exit;}
if((getenv('REQUIRE_CONSENT')?:'true')!=='false'&&($body['consent']??false)!==true){http_response_code(400);echo json_encode(['detail'=>'consent must be true']);exit;}
$byId=$path==='/v1/pin/verify-by-id';$value=strtoupper(trim((string)($byId?($body['taxpayer_id']??''):($body['pin']??''))));
if(strlen($value)<($byId?5:9)||strlen($value)>20||!preg_match('/^[A-Z0-9]+$/',$value)){http_response_code(422);echo json_encode(['detail'=>'Invalid identifier format']);exit;}
try{$service=new KraPin\KraService($env,$mock);echo json_encode($service->verify($byId,$value,strtoupper((string)($body['taxpayer_type']??'KE'))),JSON_THROW_ON_ERROR);}catch(Throwable $e){http_response_code(502);echo json_encode(['error'=>['code'=>'upstream_error','message'=>'KRA request failed']]);}
