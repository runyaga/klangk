import 'package:flterm/flterm.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'app.dart';
import 'auth/auth_service.dart';
import 'ws/ws_client.dart';
import 'utils/web_helpers_stub.dart'
    if (dart.library.html) 'utils/web_helpers_web.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (kIsWeb) {
    // libghostty's VT runs as WebAssembly in the browser; load it once before
    // any terminal is built. The bundled binary must match the resolved
    // libghostty package version or this throws.
    await initializeForWeb(
      Uri.parse('assets/assets/libghostty-wasm32-freestanding.wasm'),
    );
  }
  // Capture the hash before Flutter/GoRouter can consume it.
  final hash = getLocationHash();
  final initialLocation = (hash.length > 1) ? hash.substring(1) : '/';
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
        ChangeNotifierProxyProvider<AuthService, WsClient>(
          create: (_) => WsClient(),
          update: (_, auth, client) => client!..updateAuth(auth),
        ),
      ],
      child: KlangkApp(initialLocation: initialLocation),
    ),
  );
}
