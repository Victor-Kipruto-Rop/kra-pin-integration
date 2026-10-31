package main
import("net/http";"testing")
func TestMockLookup(t *testing.T){c:=Config{env:"sandbox",mock:true};r,e:=lookup(c,&http.Client{},false,"A000000000B","KE");if e!=nil||!r.Found||!r.Mock{t.Fatalf("%+v %v",r,e)};r,e=lookup(c,&http.Client{},false,"A999999999Z","KE");if e!=nil||r.Found{t.Fatalf("%+v %v",r,e)}}
