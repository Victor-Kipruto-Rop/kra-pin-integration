<?php
declare(strict_types=1);
use PHPUnit\Framework\TestCase;use KraPin\KraService;
final class KraServiceTest extends TestCase{
 public function testSharedCatalogContainsAll22Services():void{$catalog=json_decode(file_get_contents(__DIR__.'/../../../contracts/kra-services.json'),true,512,JSON_THROW_ON_ERROR);self::assertCount(22,$catalog['services']);}

 public function testDemoPinFound():void{$r=(new KraService('sandbox',true))->verify(false,'A000000000B','KE');self::assertTrue($r['found']);self::assertTrue($r['mock']);}
 public function testUnknownPinNotFound():void{$r=(new KraService('sandbox',true))->verify(false,'A999999999Z','KE');self::assertFalse($r['found']);}
}
