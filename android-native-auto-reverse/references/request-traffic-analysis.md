# Request And Traffic Analysis Workflow

Use this reference when the task asks for 请求分析, 接口分析, 抓包, Burp,
r0capture, objection Hook, Frida Hook, API endpoints, signing parameters,
headers, TLS pinning, WebView traffic, or Java/native request correlation.

## Output Contract

Keep these files in the analysis folder when the request surface matters:

- `static_endpoints.json`: URLs, hosts, paths, Retrofit annotations, request
  method strings, headers, WebView links, and suspicious parameter names from
  JADX/apktool/dumped dex output.
- `traffic_capture_notes.md`: device proxy/cert state, tool state, capture
  command, package, PID, Android version, and capture window.
- `burp_export/` or `burp_items.json`: Burp HTTP history export or curated raw
  requests/responses.
- `r0capture.log`: plaintext request/response/TLS evidence captured by
  r0capture.
- `hook_evidence.log`: Frida/objection output for request builders, crypto,
  signing, headers, or TLS pinning bypass experiments.
- `request_correlation.md`: static call chain to runtime request evidence,
  including unresolved params and native handoffs.
- `frida_burp_bridge.log`: Python controller output when plaintext hook points
  are routed through Burp for interactive editing.
- `mpaas_rpc_anchors`: when present in `static_endpoints.json`, review the
  mPaaS RPC section below before assuming Burp ciphertext is unrecoverable.

## Static Request Triage

Run JADX and apktool first, then extract endpoints from both decompiled Java and
resources:

```bash
apktool d -f target.apk -o apktool_out
jadx --no-debug-info --show-bad-code target.apk -d jadx_out
python3 android-native-auto-reverse/scripts/request_endpoint_extractor.py jadx_out apktool_out --out analysis/static_endpoints.json
```

Prioritize:

- URLs/domains: `https://`, `http://`, `wss://`, API host constants, CDN and
  WebView hosts.
- Retrofit: `@GET`, `@POST`, `@PUT`, `@DELETE`, `@Headers`, `@Query`,
  `@Field`, `@Body`, `@Url`.
- OkHttp: `Request.Builder`, `addHeader`, `header`, `url`, interceptors,
  `CertificatePinner`.
- WebView: `loadUrl`, `evaluateJavascript`, JS bridge names, H5 route params.
- Volley/HttpURLConnection/Apache HttpClient usage.
- mPaaS RPC: `com.alipay.mobile.common.rpc`, `RpcInvoker`, `HttpCaller`,
  `HttpUrlRequest`, `JsonSerializerV2`, `SignJsonSerializer`, `PBSerializer`,
  `Serializer.packet`, `getReqData`, `getResData`, `setResData`.
- Request signing: `sign`, `signature`, `token`, `nonce`, `timestamp`,
  `deviceId`, `encrypt`, `decrypt`, `Hmac`, `MD5`, `SHA`, `AES`, `RSA`.
- Native handoff: Java native methods near request params, JNI wrappers, or
  `.so` strings containing domains, paths, keys, and crypto terms.

If visible Java is shell-only, do not over-index the shell. Unpack first, then
rerun endpoint extraction on dumped JADX output.

## Burp Suite Capture

Use Burp when the app respects the system/user CA or can be made to trust the
test certificate in an authorized lab.

1. Configure device proxy to the Burp listener.
2. Install Burp CA into the correct store for the Android version and target
   trust model.
3. Disable QUIC/HTTP3 in the app environment when possible; otherwise note
   that traffic may bypass the HTTP proxy.
4. Clear Burp history, start the target flow, then export the relevant HTTP
   history items.
5. Save proxy/cert state and capture window in `traffic_capture_notes.md`.

Useful commands:

```bash
adb shell settings put global http_proxy 192.168.1.10:8080
adb shell settings put global http_proxy :0
adb shell settings get global http_proxy
```

If traffic is absent, distinguish:

- app not using proxy
- custom trust manager or pinning
- native TLS stack
- WebView-only traffic
- QUIC/UDP
- proxy auth/network issue
- traffic gated by login/feature state

## r0capture Capture

Use r0capture when TLS pinning, custom trust, or native TLS prevents Burp from
seeing plaintext. It is especially useful for evidence collection before
writing custom hooks.

Typical flow:

```bash
python3 r0capture.py -U -f com.example.app -v -p capture.pcap
python3 r0capture.py -U com.example.app -v
```

Record:

- package, spawn/attach mode, PID, Android version, ABI
- r0capture version/script path
- whether capture happened at startup or after manual navigation
- request URL, method, headers, body, response status/body excerpt
- any hook errors or anti-Frida symptoms

Use r0capture evidence to select exact Java/native signing functions. Do not
skip static correlation; runtime plaintext without call-chain evidence is often
not enough to reproduce signing logic.

## Frida To Burp Plaintext Bridge

Use this pattern when the network layer is encrypted/signed but Frida can see a
plaintext boundary inside the app. The boundary can be a request serializer,
business payload builder, `encrypt/sign` input, `decrypt/parse` output, or a
native JNI wrapper that receives plaintext.

Model:

```text
App hook point -> Frida send(kind/id/body/meta)
             -> Python controller
             -> synthetic HTTP item through Burp
             -> Burp edited body
             -> Python script.post(edit-kind/id/body)
             -> Frida replaces arg/return before execution continues
```

Preferred hook positions:

- Request edit: before encryption/signature generation, for example
  `Serializer.packet`, `encrypt(String)`, `sign(payload)`, request-body writer,
  or JNI method receiving plaintext.
- Response edit: after decryption and before parsing/business use, or at a
  response object setter such as `setResData`.
- Avoid editing after integrity/signature bytes are finalized unless you also
  force the app to recalculate them.

Generic controller:

```bash
python3 android-native-auto-reverse/scripts/frida_burp_crypto_bridge.py \
  --spawn com.example.app \
  --script analysis/hooks/request_crypto_bridge.js \
  --burp-host 127.0.0.1 --burp-port 8080 \
  --listen-port 28081
```

Workflow:

1. Copy `scripts/frida_crypto_bridge_template.js` into the task workspace.
2. Add target-specific hooks that call `Bridge.bridgeEdit("request", plain,
   meta)` before encryption or `Bridge.bridgeEdit("response", plain, meta)`
   after decryption.
3. Start Burp with intercept enabled.
4. Run `frida_burp_crypto_bridge.py` in spawn mode when the hook point is early
   startup; use attach mode only when late hooks are enough.
5. Edit the synthetic Burp item body and forward it. The Python controller posts
   the edited body back to the matching Frida request ID.

Bridge evidence to keep:

- Frida hook class/method/overload and whether it was request or response.
- Correlation ID, thread/PID, and body length before/after edit.
- Burp item export showing the edited plaintext.
- Whether the app recalculated signature/encryption after the edit.

## mPaaS RPC Encrypted Traffic

Use this branch when Burp shows binary/encrypted bodies and static strings point
to Alipay/mPaaS RPC classes. The common trap is hooking too late: by the time a
request reaches `HttpCaller` request data, mPaaS transport integrity/signature
work may already have happened. For request mutation, prefer the serializer
boundary before the packet is handed to the transport layer.

Recognition anchors:

- Packages/classes: `com.alipay.mobile.common.rpc`,
  `com.alipay.mobile.common.transport`, `RpcInvoker`, `HttpCaller`,
  `HttpUrlRequest`, `InnerRpcInvokeContext`.
- Serializer classes: `JsonSerializerV2`, `SignJsonSerializer`,
  `SimpleRpcJsonSerializerV2`, `PBSerializer`, `SimpleRpcPBSerializer`.
- Accessors: `Serializer.packet`, `getReqData`, `setReqData`, `getResData`,
  `setResData`.

Static and runtime order:

1. Run endpoint extraction and check `mpaas_rpc_anchors`:

   ```bash
   python3 android-native-auto-reverse/scripts/request_endpoint_extractor.py jadx_out apktool_out --out analysis/static_endpoints.json
   ```

2. If Burp only sees ciphertext, hook `Serializer.packet()` first. For JSON RPC,
   `JsonSerializerV2.packet()` is often the best early request point because it
   receives or returns the business payload before transport integrity checks.
3. Hook `RpcInvoker` to correlate the RPC method/operation, thread, packed
   body, and invoke context. This is useful for tying a Burp item back to the
   Java call chain.
4. Hook `HttpCaller`/`HttpUrlRequest` for URL, final request bytes, and response
   object evidence. Use response `getResData`/`setResData` around this layer
   when response modification is in scope.
5. Preserve request/response correlation IDs in `hook_evidence.log`; mPaaS
   calls are often concurrent, so thread-only correlation is fragile.

Observe-only probe:

```bash
frida -U -f com.example.app -l android-native-auto-reverse/scripts/frida_mpaas_rpc_probe.js --no-pause
```

The bundled probe defaults to observation. If you need edit-and-forward through
Burp in an authorized lab, copy it into the task workspace, enable blocking edit
in the copy, and run it with `frida_burp_crypto_bridge.py`. The controller
replies to Frida messages for the same request ID. Keep task-local scripts and
edited traffic in the task output directory, not in the skill.

Evidence to report:

- `mpaas_rpc_anchors` count and the class/method paths that triggered it.
- `Serializer.packet()` hook output showing plaintext or structured payload.
- `RpcInvoker` method/operation evidence when available.
- `HttpCaller` URL/final request bytes and response `getResData` evidence.
- Whether request mutation was done before or after integrity/signature work.

## Frida And objection Hook Strategy

Use Frida or objection when you need call-chain evidence, parameter values
before encryption, signature inputs/outputs, headers, or TLS bypass experiments.

Useful objection starting points:

```bash
objection -g com.example.app explore
android hooking list classes
android hooking search classes okhttp
android hooking watch class_method okhttp3.Request$Builder.url --dump-args --dump-backtrace --dump-return
android sslpinning disable
```

Useful Frida targets:

- OkHttp: `okhttp3.Request$Builder.url`, `addHeader`, `header`, `build`,
  `Interceptor.intercept`, `RequestBody.writeTo`.
- Retrofit: service interface methods, `retrofit2.OkHttpCall.execute/enqueue`.
- HttpURLConnection: `setRequestProperty`, `getOutputStream`, `connect`.
- WebView: `loadUrl`, `postUrl`, `evaluateJavascript`, JS bridge calls.
- Crypto/signing: `MessageDigest`, `Mac`, `Cipher`, Base64, app-specific
  `sign/encrypt` methods, JNI native declarations.
- Native: RegisterNatives, JNI methods near request params, OpenSSL/BoringSSL,
  custom `libcrypto*.so` or app-specific signing libraries.

For strong anti-Frida, first collect baseline Burp/r0capture/logcat evidence,
then use the least invasive hook that answers the question. If the process
exits on attach, switch to spawn timing, Florida-style Frida hardening if
available in the lab, or native/logcat crash evidence.

## Correlation Method

For every important request, build a compact table:

```text
Endpoint | Static location | Runtime evidence | Params/headers | Signing source | Native handoff | Confidence
```

Confidence labels:

- `static-candidate`: URL or method found, not observed at runtime.
- `traffic-observed`: request captured in Burp/r0capture.
- `hook-confirmed`: hook shows parameters or signature generation.
- `native-confirmed`: JNI/SO offset or function is tied to the request.
- `replay-verified`: authorized replay succeeds with understood params.

## Safety Boundaries

Only capture traffic for authorized apps, accounts, devices, and test flows.
Do not collect unrelated personal data. Redact tokens, cookies, passwords,
device identifiers, and account data in reports unless the user explicitly
needs them for authorized debugging.
