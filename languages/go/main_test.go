package main

import (
 "net/http"
 "testing"
)

func TestCatalogContainsAll22Services(t *testing.T) {
 if got:=len(serviceMutates);got!=22 { t.Fatalf("expected 22 services, got %d",got) }
 for _,id:=range []string{"authorization","pin-checker-by-pin","pin-checker-by-id","fetch-taxpayer-obligations","know-kra-tax-service-office","tax-compliance-certificate-application","tax-compliance-certificate-checker","vat-exemption-checker","it-exemption-checker","nil-return-filing","tot-return-filing","income-tax-withholding-prn-generation","vat-withholding-prn-generation","rental-withholding-prn-generation","excise-license-checker-by-pin","excise-license-checker-by-certificate-number","customs-declaration-status-checker","customs-tax-calculator","import-certificate-checker-by-pin","import-certificate-checker-by-cert-number","invoice-checker","etims-oscu-integrator-automated-testing"} {
  if _,ok:=serviceMutates[id];!ok { t.Errorf("missing service %s",id) }
 }
}

func TestUnmappedServiceDoesNotInventEndpoint(t *testing.T) {
 c:=Config{Env:"sandbox",Base:"https://sbx.kra.go.ke",Paths:map[string]string{}}
 status,_,err:=invoke(c,&http.Client{},"nil-return-filing",map[string]any{"taxPeriod":"2026"})
 if err!=nil { t.Fatal(err) }
 if status!=501 { t.Fatalf("expected 501 for unconfigured upstream mapping, got %d",status) }
}

func TestUnknownServiceIsNotCatalogued(t *testing.T) {
 if _,ok:=serviceMutates["invented-service"];ok { t.Fatal("unexpected service") }
}
