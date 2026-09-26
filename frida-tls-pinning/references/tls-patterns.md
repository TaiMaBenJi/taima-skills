# TLS Pinning Patterns

## Official And Practitioner Sources

- Frida JavaScript API: https://frida.re/docs/javascript-api/
- Frida CodeShare: https://codeshare.frida.re/
- OWASP MASTG Frida CodeShare: https://mas.owasp.org/MASTG/tools/generic/MASTG-TOOL-0032/
- OWASP MASTG Frida Android: https://mas.owasp.org/MASTG/tools/android/MASTG-TOOL-0001/
- OWASP MASTG Frida iOS: https://mas.owasp.org/MASTG/tools/ios/MASTG-TOOL-0039/

## Android Hook Order

1. Log request builders and hostnames.
2. Check OkHttp `CertificatePinner`.
3. Check Conscrypt `TrustManagerImpl`.
4. Check `SSLContext.init` trust manager replacement.
5. Check WebView SSL error callbacks.
6. Move native only when Java hooks do not fire.

## iOS Hook Order

1. Log URL/session delegates.
2. Check trust challenge callbacks.
3. Check `SecTrustEvaluateWithError` or older trust APIs.
4. Check native TLS libraries.
5. Use memory scans only after symbol/class probes fail.

## Native Hook Order

1. Enumerate modules with names matching SSL, crypto, Cronet, proxygen, Flutter, or app networking.
2. Search exports and symbols for verify, cert, trust, x509, SSL, or pin.
3. Hook return values with logs first.
4. Mutate only after the target request path is proven.
