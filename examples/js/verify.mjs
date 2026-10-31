// Node 18+. Run on a SERVER: never ship PROXY_API_KEY to a browser or mobile app.
//   PROXY_URL=http://localhost:8000 PROXY_API_KEY=dev-key node verify.mjs A000000000B
const base = process.env.PROXY_URL ?? "http://localhost:8000";
const pin = process.argv[2] ?? "A000000000B";

const res = await fetch(`${base}/v1/pin/verify`, {
  method: "POST",
  headers: { "X-API-Key": process.env.PROXY_API_KEY ?? "", "Content-Type": "application/json" },
  body: JSON.stringify({ pin, consent: true }),
});
const body = await res.json();
if (!res.ok) {
  console.error(res.status, JSON.stringify(body));
  process.exit(1);
}
console.log(body.found ? `KRA PIN found (${body.taxpayer_name})` : "KRA PIN not found");
