# Hook Output Contracts

这些是 metadata contract，不是恢复现场值的目标。URL 必须去掉 query/hash；Cookie、header、storage、body、crypto 和 canvas 内容默认只记录类型/长度。

## XHR And Fetch

```text
[spider-xhr-send] {"target":"xhr","event":"send","method":"POST","url":"https://api.example.com/data","headers":[{"name":"x-sign","valueLength":184}],"bodyType":"ArrayBuffer","bodyLength":128}
[spider-xhr-response] {"target":"xhr","event":"response","method":"POST","url":"https://api.example.com/data","status":200,"responseType":"arraybuffer","responseLength":512}
[spider-fetch-send] {"target":"fetch","event":"send","method":"POST","url":"/api/login","headers":[{"name":"authorization","valueLength":220}],"bodyType":"string","bodyLength":96}
```

Never print raw query parameters, header values, request bodies, response bodies or `Set-Cookie` values. A stack may follow only when `CONFIG.logStack` is enabled.

## Cookie And Storage

```text
[spider-cookie-set] {"name":"session-token","valueLength":192}
[spider-storage] {"target":"localStorage","event":"set","key":"auth-token","valueLength":384}
```

Cookie attributes and storage values remain hidden. `document.cookie` observation is JS-source evidence only; HTTP `Set-Cookie` still requires Network provenance.

## Crypto

```text
[spider-webcrypto] {"method":"digest","algorithm":"SHA-256","inputType":"ArrayBuffer","inputLength":32}
[spider-webcrypto-result] {"method":"digest","outputType":"ArrayBuffer","outputLength":32}
[spider-cryptojs] {"method":"SHA256","inputType":"string","inputLength":48}
```

Do not add byte previews or call arbitrary result serializers. Unknown objects use `outputLength:null`.

## Canvas Or Other Extensions

Generated project-specific hooks follow the same rule: operation name, dimensions/type and length only. A canvas data URL is represented as MIME plus total length, never a prefix preview.

## Noise Control

First narrow URL/key/method filters, then set `maxEvents` and `logStack`. There is no persistent `FULL_LOG` option. If a full value is explicitly necessary, pause once with `debugger` and inspect it without writing it to Console or a case.
