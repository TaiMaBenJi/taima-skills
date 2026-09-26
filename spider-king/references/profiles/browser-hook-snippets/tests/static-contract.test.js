const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')


const scriptsDir = path.resolve(__dirname, '..', 'scripts')
const referencesDir = path.resolve(__dirname, '..', 'references')
const files = fs.readdirSync(scriptsDir).filter((name) => name.endsWith('.js'))

for (const name of files) {
  const file = path.join(scriptsDir, name)
  execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' })
  const source = fs.readFileSync(file, 'utf8')
  assert(source.includes('maxEvents'), `${name} must cap log volume`)
  assert(source.includes('restore()'), `${name} must expose restore()`)
  assert(source.includes('__spiderHooks'), `${name} must register its lifecycle`)
  assert(!source.includes('FULL_LOG = true'), `${name} must not enable full-value logging`)
}

const network = fs.readFileSync(path.join(scriptsDir, 'xhr_fetch.js'), 'utf8')
const headers = fs.readFileSync(path.join(scriptsDir, 'cookie_header.js'), 'utf8')
const storage = fs.readFileSync(path.join(scriptsDir, 'storage.js'), 'utf8')
const crypto = fs.readFileSync(path.join(scriptsDir, 'crypto_api.js'), 'utf8')

assert(network.includes('urlIncludes') && network.includes('summarizeUrl') && network.includes('bodyLength'))
assert(headers.includes('headerNameIncludes') && headers.includes('summarizeUrl') && headers.includes('method'))
assert(network.includes('logStack: false') && headers.includes('logStack: false'))
assert(storage.includes('logStack: false') && crypto.includes('logStack: false'))
assert(storage.includes('keyIncludes') && storage.includes('valueLength'))
assert(crypto.includes('subtleMethods') && crypto.includes('getRandomValues') && crypto.includes('inputLength'))
assert(crypto.includes("['AES', 'DES', 'TripleDES', 'RC4']"))
assert(crypto.includes("['encrypt', 'decrypt']"))
assert(!crypto.includes('result.toString'), 'crypto hooks must not call arbitrary result serializers')

for (const name of fs.readdirSync(referencesDir).filter((file) => file.endsWith('.md'))) {
  const source = fs.readFileSync(path.join(referencesDir, name), 'utf8')
  assert(!/```(?:js|javascript)\b/.test(source), `${name} must not carry an untested executable snippet copy`)
}

console.log(`Hook static contracts: ok (${files.length} scripts)`)
