<?php
declare(strict_types=1);
namespace KraPin;

final class KraService {
 private string $env;
 private bool $mock;
 private string $base;
 private array $servicePaths;
 private array $serviceMethods;

 public function __construct(string $env,bool $mock) {
  $this->env=$env;$this->mock=$mock;
  $this->base=$env==='production'?'https://api.kra.go.ke':'https://sbx.kra.go.ke';
  $this->servicePaths=json_decode(getenv('KRA_SERVICE_PATHS_JSON')?:'{}',true,512,JSON_THROW_ON_ERROR);
  $this->serviceMethods=json_decode(getenv('KRA_SERVICE_METHODS_JSON')?:'{}',true,512,JSON_THROW_ON_ERROR);
 }
 private function request(string $url,array $headers=[],?array $payload=null,string $method='GET'):array {
  if($method==='GET'&&$payload!==null)$url.=(str_contains($url,'?')?'&':'?').http_build_query($payload);
  $ch=curl_init($url);$h=$headers;
  if($method==='POST')$h[]='Content-Type: application/json';
  curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>20,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_HTTPHEADER=>$h,CURLOPT_CUSTOMREQUEST=>$method,CURLOPT_POSTFIELDS=>$method==='POST'&&$payload!==null?json_encode($payload,JSON_THROW_ON_ERROR):null]);
  $raw=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);
  if($raw===false){curl_close($ch);throw new \RuntimeException('Upstream unavailable');}
  curl_close($ch);$data=json_decode($raw,true);
  if(!is_array($data))throw new \RuntimeException('Unexpected upstream response');
  return [$status,$data];
 }
 private function token(string $key,string $secret,bool $force=false):string {
  static $cache=[];
  if(!$force&&isset($cache[$key])&&$cache[$key]['expires']>time()+60)return $cache[$key]['value'];
  [$status,$data]=$this->request($this->base.'/v1/token/generate?grant_type=client_credentials',['Authorization'=>'Basic '.base64_encode($key.':'.$secret)]);
  if($status>=400||empty($data['access_token']))throw new \RuntimeException('KRA authorization failed');
  $cache[$key]=['value'=>$data['access_token'],'expires'=>time()+(int)($data['expires_in']??3600)];
  return $cache[$key]['value'];
 }
 public function invokeCatalog(string $service,array $payload):array {
  $key=getenv('KRA_PIN_CONSUMER_KEY')?:'';$secret=getenv('KRA_PIN_CONSUMER_SECRET')?:'';
  if($service==='authorization'){$this->token($key,$secret);return [200,['authorized'=>true,'token_type'=>'Bearer']];}
  $path=$this->servicePaths[$service]??null;
  if(!is_string($path)||!str_starts_with($path,'/')||str_starts_with($path,'//'))return [501,['error'=>['code'=>'service_not_configured','message'=>'No verified KRA endpoint mapping configured']]];
  $method=strtoupper($this->serviceMethods[$service]??'POST');
  if(!in_array($method,['GET','POST'],true)||($method==='GET'&&in_array($service,['tax-compliance-certificate-application','nil-return-filing','tot-return-filing','income-tax-withholding-prn-generation','vat-withholding-prn-generation','rental-withholding-prn-generation','etims-oscu-integrator-automated-testing'],true)))return [501,['detail'=>'Unsupported or unsafe configured HTTP method']];
  $upstreamBase=$this->base;
  $parts=parse_url($upstreamBase);
  if(!is_array($parts)||($parts['scheme']??'')!=='https'||!str_ends_with((string)($parts['host']??''),'.kra.go.ke'))return [501,['error'=>['code'=>'service_base_not_configured','message'=>'Set a verified HTTPS KRA base URL for this service']]];
  $access=$this->token($key,$secret);
  [$status,$data]=$this->request(rtrim($upstreamBase,'/').$path,['Authorization: Bearer '.$access],$payload,$method);
  if($status===401){$access=$this->token($key,$secret,true);[$status,$data]=$this->request(rtrim($upstreamBase,'/').$path,['Authorization: Bearer '.$access],$payload,$method);}
  if($status>=400)return [$status===429?429:502,['error'=>['code'=>'kra_upstream_error','message'=>'KRA service request failed']]];
  return [200,$data];
 }
 public function verify(bool $byId,string $value,string $type):array {
  if($this->mock){$found=$byId?$value==='00000000':$value==='A000000000B';return ['found'=>$found,'pin'=>$found?'A000000000B':null,'taxpayer_name'=>$found?'DEMO T*****':null,'environment'=>$this->env,'mock'=>true,'raw'=>null];}
  $key=getenv($byId?'KRA_PIN_BY_ID_CONSUMER_KEY':'KRA_PIN_CONSUMER_KEY')?:getenv('KRA_PIN_CONSUMER_KEY');
  $secret=getenv($byId?'KRA_PIN_BY_ID_CONSUMER_SECRET':'KRA_PIN_CONSUMER_SECRET')?:getenv('KRA_PIN_CONSUMER_SECRET');
  $t=$this->token((string)$key,(string)$secret);$path=$byId?'/checker/v1/pin':'/checker/v1/pinbypin';
  $payload=$byId?['TaxpayerType'=>$type,'TaxpayerID'=>$value]:['KRAPIN'=>$value];
  [$status,$data]=$this->request($this->base.$path,['Authorization: Bearer '.$t],$payload,'POST');
  if($status===404||($status>=400&&(string)($data['errorCode']??'')==='30002'))return ['found'=>false,'pin'=>null,'taxpayer_name'=>null,'environment'=>$this->env,'mock'=>false,'raw'=>null];
  $record=$data['PINDATA']??$data;$pin=$record['KRAPIN']??null;$name=$record['Name']??null;
  if($status>=400||(!$pin&&!$name))throw new \RuntimeException('Unexpected KRA response shape');
  return ['found'=>true,'pin'=>$pin,'taxpayer_name'=>$name,'environment'=>$this->env,'mock'=>false,'raw'=>null];
 }
}
