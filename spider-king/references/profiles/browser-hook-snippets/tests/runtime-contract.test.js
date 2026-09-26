const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')


const scriptsDir = path.resolve(__dirname, '..', 'scripts')

function createSandbox() {
  const logs = []
  class Headers {
    constructor(init) {
      this.values = new Map()
      if (init instanceof Headers) init.forEach((value, name) => this.values.set(name, value))
      else if (Array.isArray(init)) init.forEach(([name, value]) => this.values.set(String(name), String(value)))
      else if (init && typeof init === 'object') Object.entries(init).forEach(([name, value]) => this.values.set(name, String(value)))
    }
    forEach(callback) { this.values.forEach((value, name) => callback(value, name)) }
  }

  class XMLHttpRequest {
    constructor() { this.status = 200; this.responseText = 'ok'; this.listeners = {} }
    open() {}
    send() { if (this.listeners.load) this.listeners.load.call(this) }
    setRequestHeader() {}
    addEventListener(name, callback) { this.listeners[name] = callback }
  }

  class Document {
    constructor() { this.cookieValue = '' }
  }
  Object.defineProperty(Document.prototype, 'cookie', {
    configurable: true,
    get() { return this.cookieValue },
    set(value) { this.cookieValue = String(value) },
  })

  class Storage {
    constructor() { this.values = new Map() }
    setItem(key, value) { this.values.set(String(key), String(value)) }
    getItem(key) { return this.values.has(String(key)) ? this.values.get(String(key)) : null }
    removeItem(key) { this.values.delete(String(key)) }
  }

  class SubtleCrypto {
    digest() { return Promise.resolve(new Uint8Array([1, 2]).buffer) }
    sign() { return Promise.resolve(new Uint8Array([3]).buffer) }
    encrypt() { return Promise.resolve(new Uint8Array([4]).buffer) }
    decrypt() { return Promise.resolve(new Uint8Array([5]).buffer) }
  }
  class Crypto {
    getRandomValues(array) { return array }
  }

  function cipherFixture() {
    return {
      encrypt() { return { ciphertext: { sigBytes: 16 }, toString() { throw new Error('serializer must not be called') } } },
      decrypt() { return { sigBytes: 7, toString() { throw new Error('serializer must not be called') } } },
    }
  }

  const sandbox = {
    console: {
      log(...args) { logs.push(['log', ...args]) },
      trace(...args) { logs.push(['trace', ...args]) },
      warn(...args) { logs.push(['warn', ...args]) },
      error(...args) { logs.push(['error', ...args]) },
    },
    Headers,
    XMLHttpRequest,
    Document,
    HTMLDocument: Document,
    document: new Document(),
    Storage,
    localStorage: new Storage(),
    sessionStorage: new Storage(),
    SubtleCrypto,
    Crypto,
    crypto: new Crypto(),
    CryptoJS: {
      SHA256() { return { toString() { throw new Error('serializer must not be called') } } },
      AES: cipherFixture(),
      DES: cipherFixture(),
      TripleDES: cipherFixture(),
      RC4: cipherFixture(),
    },
    fetch() { return Promise.resolve({ status: 200 }) },
    Uint8Array,
    ArrayBuffer,
    Promise,
    __logs: logs,
  }
  sandbox.crypto.subtle = new SubtleCrypto()
  sandbox.window = sandbox
  sandbox.globalThis = sandbox
  return vm.createContext(sandbox)
}

function install(context, name) {
  const source = fs.readFileSync(path.join(scriptsDir, name), 'utf8')
  vm.runInContext(source, context, { filename: name })
}

async function main() {
  {
    const context = createSandbox()
    const originalOpen = context.XMLHttpRequest.prototype.open
    const originalFetch = context.fetch
    install(context, 'xhr_fetch.js')
    const xhr = new context.XMLHttpRequest()
    xhr.open('POST', '/api/test?token=TOPSECRET')
    xhr.setRequestHeader('x-sign', 'secret')
    xhr.send(new context.ArrayBuffer(8))
    const binaryXhr = new context.XMLHttpRequest()
    binaryXhr.open('GET', '/api/binary')
    binaryXhr.responseType = 'arraybuffer'
    binaryXhr.response = new Uint8Array([1, 2]).buffer
    Object.defineProperty(binaryXhr, 'responseText', { get() { throw new Error('InvalidStateError') } })
    assert.doesNotThrow(() => binaryXhr.send())
    await context.fetch('/api/test?token=TOPSECRET', { method: 'POST', headers: { 'x-sign': 'secret' }, body: new context.ArrayBuffer(8) })
    const networkLogs = JSON.stringify(context.__logs)
    assert(!networkLogs.includes('TOPSECRET'))
    const networkPayloads = context.__logs
      .filter((entry) => entry[0] === 'log' && typeof entry[2] === 'string' && entry[2].startsWith('{'))
      .map((entry) => JSON.parse(entry[2]))
    assert(networkPayloads.some((payload) => payload.bodyLength === 8))
    assert(!context.__logs.some((entry) => entry[0] === 'trace'))
    context.__spiderHooks.xhrFetch.restore()
    assert.equal(context.XMLHttpRequest.prototype.open, originalOpen)
    assert.equal(context.fetch, originalFetch)
  }

  {
    const context = createSandbox()
    let issuedPromise
    context.fetch = function () {
      issuedPromise = Promise.resolve({ status: 204 })
      return issuedPromise
    }
    install(context, 'xhr_fetch.js')
    const returnedPromise = context.fetch('/api/identity')
    assert.equal(returnedPromise, issuedPromise, 'fetch hook must preserve Promise identity')
    await returnedPromise
    assert(!context.__logs.some((entry) => String(entry[1]).includes('spider-fetch-response')))
    context.__spiderHooks.xhrFetch.restore()
  }

  {
    const context = createSandbox()
    let urlConversions = 0
    let headerConversions = 0
    context.XMLHttpRequest.prototype.open = function (_method, url) { String(url) }
    context.XMLHttpRequest.prototype.setRequestHeader = function (_name, value) { String(value) }
    install(context, 'xhr_fetch.js')
    const xhr = new context.XMLHttpRequest()
    xhr.open('GET', { toString() { urlConversions += 1; return '/api/once' } })
    xhr.setRequestHeader('x-sign', { toString() { headerConversions += 1; return 'value' } })
    assert.equal(urlConversions, 1, 'hook must not coerce XHR URL arguments twice')
    assert.equal(headerConversions, 1, 'hook must not coerce XHR header values twice')
    context.__spiderHooks.xhrFetch.restore()
  }

  {
    const context = createSandbox()
    const originalOpen = context.XMLHttpRequest.prototype.open
    install(context, 'cookie_header.js')
    context.document.cookie = 'token=secret; Path=/'
    const xhr = new context.XMLHttpRequest()
    xhr.open('GET', '/api/test?token=TOPSECRET')
    xhr.setRequestHeader('Authorization', 'secret')
    const headerLogs = JSON.stringify(context.__logs)
    assert(!headerLogs.includes('TOPSECRET'))
    assert(!headerLogs.includes('secret'))
    assert(!context.__logs.some((entry) => entry[0] === 'trace'))
    context.__spiderHooks.cookieHeader.restore()
    assert.equal(context.XMLHttpRequest.prototype.open, originalOpen)
    assert.equal(context.document.cookie, 'token=secret; Path=/')
  }

  {
    const context = createSandbox()
    const originalSetItem = context.Storage.prototype.setItem
    install(context, 'storage.js')
    context.localStorage.setItem('auth-token', 'secret')
    assert(!context.__logs.some((entry) => entry[0] === 'trace'))
    context.__spiderHooks.storage.restore()
    assert.equal(context.Storage.prototype.setItem, originalSetItem)
  }

  {
    const context = createSandbox()
    const originalDigest = context.SubtleCrypto.prototype.digest
    const originalSha256 = context.CryptoJS.SHA256
    const cipherFamilies = ['AES', 'DES', 'TripleDES', 'RC4']
    const cipherOriginals = new Map(cipherFamilies.map((family) => [family, {
      encrypt: context.CryptoJS[family].encrypt,
      decrypt: context.CryptoJS[family].decrypt,
    }]))
    install(context, 'crypto_api.js')
    await context.crypto.subtle.digest({ name: 'SHA-256' }, new Uint8Array([1, 2]))
    context.crypto.getRandomValues(new Uint8Array(2))
    assert.doesNotThrow(() => context.CryptoJS.SHA256('secret'))
    for (const family of cipherFamilies) {
      assert.doesNotThrow(() => context.CryptoJS[family].encrypt('PLAINTEXT_LEAK_PROBE', 'KEY_LEAK_PROBE', { iv: 'IV_LEAK_PROBE' }))
      assert.doesNotThrow(() => context.CryptoJS[family].decrypt({ ciphertext: { sigBytes: 16 } }, 'KEY_LEAK_PROBE', { iv: 'IV_LEAK_PROBE' }))
    }
    const cryptoLogs = JSON.stringify(context.__logs)
    for (const family of cipherFamilies) {
      assert(cryptoLogs.includes(family + '.encrypt'))
      assert(cryptoLogs.includes(family + '.decrypt'))
    }
    assert(!cryptoLogs.includes('TOPSECRET'))
    assert(!cryptoLogs.includes('secret'))
    assert(!cryptoLogs.includes('key'))
    assert(!cryptoLogs.includes('PLAINTEXT_LEAK_PROBE'))
    assert(!cryptoLogs.includes('KEY_LEAK_PROBE'))
    assert(!cryptoLogs.includes('IV_LEAK_PROBE'))
    assert(!context.__logs.some((entry) => entry[0] === 'trace'))
    context.__spiderHooks.cryptoApi.restore()
    assert.equal(context.SubtleCrypto.prototype.digest, originalDigest)
    assert.equal(context.CryptoJS.SHA256, originalSha256)
    for (const family of cipherFamilies) {
      assert.equal(context.CryptoJS[family].encrypt, cipherOriginals.get(family).encrypt)
      assert.equal(context.CryptoJS[family].decrypt, cipherOriginals.get(family).decrypt)
    }
  }

  {
    const context = createSandbox()
    let metadataGetterCalls = 0
    const result = {}
    Object.defineProperty(result, 'sigBytes', {
      get() {
        metadataGetterCalls += 1
        throw new Error('observer getter executed')
      },
    })
    context.CryptoJS.SHA256 = function () { return result }
    install(context, 'crypto_api.js')
    assert.equal(context.CryptoJS.SHA256('fixture'), result)
    assert.equal(metadataGetterCalls, 0)
    context.__spiderHooks.cryptoApi.restore()
  }

  {
    const context = createSandbox()
    const originalPromise = Promise.resolve(new Uint8Array([9]).buffer)
    context.SubtleCrypto.prototype.digest = function () { return originalPromise }
    install(context, 'crypto_api.js')
    const returnedPromise = context.crypto.subtle.digest({ name: 'SHA-256' }, new Uint8Array([1]))
    assert.equal(returnedPromise, originalPromise)
    await returnedPromise
    context.__spiderHooks.cryptoApi.restore()
  }

  {
    const context = createSandbox()
    install(context, 'crypto_api.js')
    await context.crypto.subtle.digest('TOPSECRET_ALGORITHM_ARGUMENT', new Uint8Array([1]))
    const logs = JSON.stringify(context.__logs)
    assert(!logs.includes('TOPSECRET_ALGORITHM_ARGUMENT'))
    const event = context.__logs.find((entry) => entry[1] === '[spider-webcrypto]')
    assert.equal(JSON.parse(event[2]).algorithm, 'other')
    context.__spiderHooks.cryptoApi.restore()
  }

  console.log('Hook runtime contracts: ok')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
