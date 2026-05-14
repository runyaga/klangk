import 'package:web/web.dart' as web;

/// Get the base path from the HTML <base href> element.
/// Returns '' for root, '/bark' for subpath (no trailing slash).
String get baseUrl {
  final bases = web.document.getElementsByTagName('base');
  if (bases.length > 0) {
    final href = (bases.item(0)! as web.HTMLBaseElement).href;
    // href is fully resolved, e.g. "http://localhost:8997/" or "https://arctor.repoze.org/bark/"
    final uri = Uri.parse(href);
    var path = uri.path;
    if (path.endsWith('/')) path = path.substring(0, path.length - 1);
    return path; // '' for root, '/bark' for subpath
  }
  return '';
}
