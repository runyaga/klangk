import 'dart:async';
import 'dart:js_interop';
import 'dart:typed_data';
import 'package:flutter/widgets.dart';
import 'package:web/web.dart' as web;

/// Open a URL in a new browser tab.
void openUrl(String url) {
  web.window.open(url, '_blank');
}

/// Download bytes as a file via a temporary blob URL.
void downloadBytes(List<int> bytes, String filename) {
  final parts = [Uint8List.fromList(bytes).toJS].toJS;
  final blob = web.Blob(parts);
  final blobUrl = web.URL.createObjectURL(blob);
  final anchor = web.HTMLAnchorElement()
    ..href = blobUrl
    ..download = filename;
  anchor.click();
  web.URL.revokeObjectURL(blobUrl);
}

/// Briefly suppress the browser context menu (for right-click handling).
void suppressContextMenuBriefly() {
  final handler = ((web.Event e) {
    e.preventDefault();
  }).toJS;
  web.document.addEventListener('contextmenu', handler);
  Future.delayed(const Duration(milliseconds: 100), () {
    web.document.removeEventListener('contextmenu', handler);
  });
}

/// Get the browser's location hash fragment.
String getLocationHash() => web.window.location.hash;

/// Web implementation — suppresses native browser context menu on right-click.
Widget buildSuppressor(Widget child) {
  return Listener(
    onPointerDown: (event) {
      if (event.buttons == 2) {
        suppressContextMenuBriefly();
      }
    },
    child: child,
  );
}
