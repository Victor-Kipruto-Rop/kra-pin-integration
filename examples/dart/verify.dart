// Dart server or CLI using package:http. Untested sketch.
// In a Flutter app, call YOUR backend instead; never embed the proxy API key in the app.
//
//   dart pub add http
//   PROXY_URL=http://localhost:8000 PROXY_API_KEY=dev-key dart run verify.dart A000000000B
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

Future<void> main(List<String> args) async {
  final base = Platform.environment['PROXY_URL'] ?? 'http://localhost:8000';
  final pin = args.isNotEmpty ? args.first : 'A000000000B';

  final res = await http.post(
    Uri.parse('$base/v1/pin/verify'),
    headers: {
      'X-API-Key': Platform.environment['PROXY_API_KEY'] ?? '',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({'pin': pin, 'consent': true}),
  );
  if (res.statusCode != 200) {
    stderr.writeln('${res.statusCode}: ${res.body}');
    exit(1);
  }
  final body = jsonDecode(res.body) as Map<String, dynamic>;
  print(body['found'] == true ? 'KRA PIN found' : 'KRA PIN not found');
}
