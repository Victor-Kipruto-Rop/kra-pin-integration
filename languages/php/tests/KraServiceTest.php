<?php
declare(strict_types=1);
use PHPUnit\Framework\TestCase;use KraPin\KraService;
final class KraServiceTest extends TestCase{
 public function testDemoPinFound():void{$r=(new KraService('sandbox',true))->verify(false,'A000000000B','KE');self::assertTrue($r['found']);self::assertTrue($r['mock']);}
 public function testUnknownPinNotFound():void{$r=(new KraService('sandbox',true))->verify(false,'A999999999Z','KE');self::assertFalse($r['found']);}
}
