// coverage:ignore-file

/// Whether the browser supports speech recognition.
bool isSpeechRecognitionSupported() => false;

/// Start speech recognition — unsupported outside browser.
SpeechSession startSpeechRecognition({String lang = 'en-US'}) {
  throw UnsupportedError('Speech recognition not available');
}

class SpeechSession {
  Stream<String> get transcripts => const Stream.empty();
  bool get isActive => false;
  void start() {}
  void stop() {}
}
