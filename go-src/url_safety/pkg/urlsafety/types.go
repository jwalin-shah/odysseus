// Package urlsafety implements outbound URL safety checks for SSRF hardening.
//
// The Go port mirrors src/url_safety.py: it validates user-supplied URLs
// before the server makes an outbound HTTP request. The checks in order are:
//
//  1. The scheme must be http or https (file://, gopher://, ftp://, etc.
//     are rejected).
//  2. The host must be present and non-empty.
//  3. The host must resolve (A + AAAA records) via the configured
//     Resolver. Tests inject a stub Resolver so they don't hit DNS.
//  4. Every resolved IP is classified. Link-local addresses
//     (169.254.0.0/16, fe80::/10) are always rejected — that is the cloud
//     instance-metadata SSRF credential-exfil vector. Multicast, reserved,
//     and unspecified addresses are rejected too.
//  5. When BlockPrivate is true, additional private/loopback ranges
//     (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, ::1, ...)
//     are also rejected. The default is false because Odysseus is
//     local-first and pointing an embedding endpoint at a local
//     vLLM/llama.cpp/Ollama server is a normal, intended use case.
//
// IPv4-mapped IPv6 addresses (e.g. ::ffff:169.254.169.254) are unwrapped
// before classification so the embedded IPv4 is judged, not the IPv6
// wrapper. IPv6 zone IDs (e.g. fe80::1%eth0) are stripped before parsing.
package urlsafety
