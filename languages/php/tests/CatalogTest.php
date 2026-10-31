<?php
declare(strict_types=1);
use PHPUnit\Framework\TestCase;
require_once __DIR__ . '/../src/KraService.php';

final class CatalogTest extends TestCase {
 public function testCatalogReturnsNotConfiguredInsteadOfGuessingEndpoint(): void {
  putenv('KRA_SERVICE_PATHS_JSON={}');putenv('KRA_SERVICE_METHODS_JSON={}');
  $service=new \KraPin\KraService('sandbox',false);
  [$status,$body]=$service->invokeCatalog('nil-return-filing',['tax_period'=>'2026']);
  self::assertSame(501,$status);
  self::assertSame('service_not_configured',$body['error']['code']);
 }
 public function testUnknownServiceCannotBeMappedByDefault(): void {
  putenv('KRA_SERVICE_PATHS_JSON={}');
  $service=new \KraPin\KraService('sandbox',false);
  [$status]=$service->invokeCatalog('made-up-service',[]);
  self::assertSame(501,$status);
 }
}
