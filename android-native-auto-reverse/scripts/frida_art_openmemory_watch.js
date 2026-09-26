/*
 * Authorized ART OpenMemory/OpenDexFilesFromOat watcher.
 *
 * Purpose:
 * - Locate common ART dex loading and verifier symbols at runtime.
 * - Log OpenDexFilesFromOat/OpenMemory/DexFileVerifier calls.
 * - Heuristically dump arguments that point to an in-memory DEX buffer.
 *
 * Use when a shell such as Bangcle/SecNeo creates placeholder dex files and
 * feeds the real DEX to ART through DexFile::OpenMemory or related loaders.
 */

'use strict';

const OUTPUT_DIR = '/data/local/tmp';
const MAX_DUMP_SIZE = 128 * 1024 * 1024;
const MIN_DUMP_SIZE = 0x70;
const MAX_ARGS_TO_SCAN = 8;

const SYMBOL_PATTERNS = [
  /OpenDexFilesFromOat/i,
  /OpenMemory/i,
  /DexFileVerifier.*Verify/i,
  /openInMemoryDexFilesNative/i,
];

const hooked = {};
let dumpIndex = 0;

function log(message) {
  console.log('[art-openmemory] ' + message);
}

function safeSymbol(address) {
  try {
    return DebugSymbol.fromAddress(address).toString();
  } catch (_) {
    return address.toString();
  }
}

function sanitize(text) {
  return text.replace(/[^A-Za-z0-9_.-]/g, '_').slice(0, 160);
}

function looksLikeDex(ptrValue) {
  try {
    if (ptrValue.isNull()) return null;
    const magic = ptrValue.readByteArray(8);
    const bytes = new Uint8Array(magic);
    if (bytes[0] !== 0x64 || bytes[1] !== 0x65 || bytes[2] !== 0x78 || bytes[3] !== 0x0a) {
      return null;
    }
    const size = ptrValue.add(0x20).readU32();
    if (size < MIN_DUMP_SIZE || size > MAX_DUMP_SIZE) {
      return null;
    }
    return size;
  } catch (_) {
    return null;
  }
}

function dumpDex(ptrValue, size, tag) {
  try {
    const out = OUTPUT_DIR + '/dex_' + Process.id + '_' + dumpIndex + '_' + sanitize(tag) + '_' + ptrValue + '_' + size + '.dex';
    dumpIndex += 1;
    const data = ptrValue.readByteArray(size);
    const file = new File(out, 'wb');
    file.write(data);
    file.flush();
    file.close();
    log('dumped dex ptr=' + ptrValue + ' size=' + size + ' out=' + out);
  } catch (e) {
    log('dump failed ptr=' + ptrValue + ' size=' + size + ': ' + e);
  }
}

function scanArgsForDex(args, tag) {
  for (let i = 0; i < MAX_ARGS_TO_SCAN; i += 1) {
    const p = args[i];
    const directSize = looksLikeDex(p);
    if (directSize !== null) {
      log(tag + ' arg[' + i + '] direct dex ptr=' + p + ' size=' + directSize);
      dumpDex(p, directSize, tag + '_arg' + i);
      continue;
    }

    try {
      if (!p.isNull()) {
        const indirect = p.readPointer();
        const indirectSize = looksLikeDex(indirect);
        if (indirectSize !== null) {
          log(tag + ' arg[' + i + '] indirect dex ptr=' + indirect + ' size=' + indirectSize);
          dumpDex(indirect, indirectSize, tag + '_arg' + i + '_indirect');
        }
      }
    } catch (_) {
    }
  }
}

function hookSymbol(sym) {
  const key = sym.address.toString();
  if (hooked[key]) return;
  hooked[key] = true;
  const tag = sym.name;
  try {
    Interceptor.attach(sym.address, {
      onEnter(args) {
        log('enter ' + tag + ' @ ' + sym.address);
        scanArgsForDex(args, tag);
      },
      onLeave(retval) {
        log('leave ' + tag + ' retval=' + retval);
      },
    });
    log('hooked ' + tag + ' @ ' + sym.address);
  } catch (e) {
    log('hook failed ' + tag + ' @ ' + sym.address + ': ' + e);
  }
}

function hookArtSymbols() {
  const art = Process.findModuleByName('libart.so');
  if (art === null) {
    log('libart.so not loaded yet');
    return;
  }
  let count = 0;
  const symbols = Module.enumerateSymbolsSync ? Module.enumerateSymbolsSync('libart.so') : Module.enumerateSymbols('libart.so');
  symbols.forEach(function (sym) {
    if (sym.type !== 'function') return;
    if (!SYMBOL_PATTERNS.some(function (rx) { return rx.test(sym.name); })) return;
    hookSymbol(sym);
    count += 1;
  });
  log('ART hook candidates=' + count);
}

function hookMprotect() {
  const fn = Module.findExportByName(null, 'mprotect') || Module.findExportByName('libc.so', 'mprotect');
  if (fn === null) return;
  Interceptor.attach(fn, {
    onEnter(args) {
      this.addr = args[0];
      this.size = args[1].toUInt32 ? args[1].toUInt32() : args[1].toInt32();
      this.prot = args[2].toInt32();
    },
    onLeave(retval) {
      if ((this.prot & 4) !== 0) {
        log('mprotect RX addr=' + this.addr + ' size=' + this.size + ' prot=0x' + this.prot.toString(16) + ' ret=' + retval);
      }
    },
  });
  log('hooked mprotect');
}

function hookNativeLoaders() {
  ['android_dlopen_ext', 'dlopen'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) return;
    Interceptor.attach(fn, {
      onEnter(args) {
        this.path = args[0].isNull() ? '' : args[0].readCString();
      },
      onLeave(retval) {
        if (this.path) {
          log(name + '(' + this.path + ') => ' + retval);
          if (this.path.indexOf('libart.so') !== -1) {
            setTimeout(hookArtSymbols, 0);
          }
        }
      },
    });
  });
}

setImmediate(function () {
  log('starting pid=' + Process.id + ' arch=' + Process.arch + ' out=' + OUTPUT_DIR);
  hookNativeLoaders();
  hookMprotect();
  hookArtSymbols();
  setTimeout(hookArtSymbols, 1000);
});
