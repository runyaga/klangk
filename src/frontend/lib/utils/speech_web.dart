import 'dart:async';
import 'dart:html' as html;
import 'dart:js_util' as js_util;

// coverage:ignore-file

/// Whether the browser supports speech recognition.
bool isSpeechRecognitionSupported() {
  return js_util.hasProperty(html.window, 'webkitSpeechRecognition') ||
      js_util.hasProperty(html.window, 'SpeechRecognition');
}

/// Start speech recognition. Returns a [SpeechSession] whose [transcripts]
/// stream emits final transcript strings. The stream closes when recognition
/// stops (via [stop], silence, or error).
SpeechSession startSpeechRecognition({String lang = 'en-US'}) {
  return SpeechSession._(lang: lang);
}

class SpeechSession {
  final StreamController<String> _controller = StreamController<String>();
  dynamic _recognition;
  bool _active = false;

  SpeechSession._({String lang = 'en-US'}) {
    final constructor =
        js_util.getProperty(html.window, 'webkitSpeechRecognition') ??
            js_util.getProperty(html.window, 'SpeechRecognition');
    _recognition = js_util.callConstructor(constructor, []);

    js_util.setProperty(_recognition, 'continuous', true);
    js_util.setProperty(_recognition, 'interimResults', false);
    js_util.setProperty(_recognition, 'lang', lang);

    js_util.setProperty(_recognition, 'onresult', js_util.allowInterop((event) {
      final results = js_util.getProperty(event, 'results');
      final length = js_util.getProperty(results, 'length') as int;
      for (var i = 0; i < length; i++) {
        final result = js_util.callMethod(results, 'item', [i]);
        final isFinal = js_util.getProperty(result, 'isFinal') as bool;
        if (isFinal) {
          final alt = js_util.callMethod(result, 'item', [0]);
          final transcript = js_util.getProperty(alt, 'transcript') as String;
          _controller.add(transcript.trim());
        }
      }
    }));

    js_util.setProperty(_recognition, 'onerror', js_util.allowInterop((event) {
      final error = js_util.getProperty(event, 'error') as String;
      if (error != 'no-speech' && error != 'aborted') {
        _controller.addError(error);
      }
      _active = false;
    }));

    js_util.setProperty(_recognition, 'onend', js_util.allowInterop((_) {
      _active = false;
      _controller.close();
    }));
  }

  Stream<String> get transcripts => _controller.stream;
  bool get isActive => _active;

  void start() {
    js_util.callMethod(_recognition, 'start', []);
    _active = true;
  }

  void stop() {
    if (_active) {
      js_util.callMethod(_recognition, 'stop', []);
      _active = false;
    }
  }
}
