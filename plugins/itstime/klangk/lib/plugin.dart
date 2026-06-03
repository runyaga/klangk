import 'dart:js_interop';

import 'package:flutter/material.dart';
import 'package:klangk_plugin_api/klangk_plugin_api.dart';

@JS('eval')
external JSAny? _eval(JSString code);

class ItsTimePlugin extends ToolPlugin with ChangeNotifier {
  bool _show = false;

  @override
  Map<String, ToolHandler> get handlers => {'itstime': _handle};

  Future<String> _handle(Map<String, dynamic> request) async {
    _show = true;
    notifyListeners();
    return "It's time to stop.";
  }

  @override
  Widget? buildOverlay(BuildContext context) {
    return _ItsTimeOverlay(plugin: this);
  }
}

class _ItsTimeOverlay extends StatefulWidget {
  final ItsTimePlugin plugin;
  const _ItsTimeOverlay({required this.plugin});

  @override
  State<_ItsTimeOverlay> createState() => _ItsTimeOverlayState();
}

class _ItsTimeOverlayState extends State<_ItsTimeOverlay> {
  @override
  void initState() {
    super.initState();
    widget.plugin.addListener(_onUpdate);
  }

  @override
  void dispose() {
    _destroyVideo();
    widget.plugin.removeListener(_onUpdate);
    super.dispose();
  }

  void _onUpdate() {
    if (widget.plugin._show) {
      _createVideo();
    }
    if (mounted) setState(() {});
  }

  void _createVideo() {
    // Asset URL in Flutter web build
    final assetUrl = 'assets/packages/klangk_plugin_itstime/assets/itstime.mp4';
    final js =
        '''
      (function() {
        if (document.getElementById('itstime-overlay')) return;
        var overlay = document.createElement('div');
        overlay.id = 'itstime-overlay';
        overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;cursor:pointer;';
        var video = document.createElement('video');
        video.src = '$assetUrl';
        video.autoplay = true;
        video.style.cssText = 'max-width:80vw;max-height:80vh;border-radius:8px;box-shadow:0 0 40px rgba(0,0,0,0.8);';
        overlay.appendChild(video);
        overlay.addEventListener('click', function() {
          video.pause();
          overlay.remove();
        });
        video.addEventListener('ended', function() {
          overlay.remove();
        });
        document.body.appendChild(overlay);
      })()
    ''';
    _eval(js.toJS);
  }

  void _destroyVideo() {
    final js = '''
      (function() {
        var el = document.getElementById('itstime-overlay');
        if (el) { var v = el.querySelector('video'); if (v) v.pause(); el.remove(); }
      })()
    ''';
    _eval(js.toJS);
  }

  void _dismiss() {
    _destroyVideo();
    widget.plugin._show = false;
    widget.plugin.notifyListeners();
  }

  @override
  Widget build(BuildContext context) {
    // Video is rendered via DOM overlay, so the Flutter widget just
    // provides a tap target to dismiss and notifies plugin state.
    // The actual video element is managed in JS for autoplay support.
    if (!widget.plugin._show) return const SizedBox.shrink();
    return const SizedBox.shrink();
  }
}
