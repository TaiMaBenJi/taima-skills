/*
 * Authorized Bangcle/libDexHelper anti-Frida triage template.
 *
 * Copy this file into the task workspace and edit TARGET_LIB, TARGET_OFFSETS,
 * keyword filters, and patch behavior for the specific sample. Keep sample
 * offsets out of the skill directory.
 *
 * Example:
 *   frida -U -f com.example.app -l analysis/frida_bangcle_dexhelper_antifrida.target.js --no-pause
 */

'use strict';

const TARGET_LIB = 'libDexHelper.so';

// Sample-specific image offsets. Fill these after IDA/Ghidra + maps evidence.
const TARGET_OFFSETS = [
  // { name: 'maps_scan', offset: 0x0, arch: 'arm64', patch: 'ret' },
  // { name: 'exit_group_kill', offset: 0x0, arch: 'arm64', patch: 'ret' },
];

// Sample-specific thread start offsets. Fill only after clone/pthread evidence.
const DETECTION_THREAD_OFFSETS = [
  // { offset: 0x0, action: 'ret', reason: 'confirmed libDexHelper detection worker' },
];

const HIDE_KEYWORDS = [
  'frida',
  'gum-js-loop',
  'gum-js',
  'florida',
  '.fs64',
  'gmain',
  'gdbus',
  'gadget',
  're.frida',
  'linjector',
  'magisk',
  'zygisk',
  'shamiko',
  'kernelsu',
  'ksu',
  'xposed',
  'lsposed',
];

const BLOCK_PORTS = [27042, 27043, 29123];
const BIONIC_PTHREAD_START_OFFSET = 0x60;

const ROOT_PATHS = [
  '/sbin/su',
  '/system/bin/su',
  '/system/xbin/su',
  '/vendor/bin/su',
  '/su/bin/su',
  '/data/adb/magisk',
  '/data/adb/ksu',
  '/data/adb/kernelsu',
  '/sbin/.magisk',
  '/system/app/Superuser.apk',
  '/system/app/Magisk.apk',
  '/system/bin/busybox',
  '/system/xbin/busybox',
];

function log(message) {
  console.log('[bangcle-antifrida] ' + message);
}

function moduleBase() {
  const mod = Process.findModuleByName(TARGET_LIB);
  return mod ? mod.base : null;
}

function writeReturn(address, arch) {
  Memory.patchCode(address, 16, function (code) {
    if (arch === 'arm64') {
      const writer = new Arm64Writer(code, { pc: address });
      writer.putRet();
      writer.flush();
    } else if (arch === 'arm') {
      const writer = new ThumbWriter(code, { pc: address.or(1) });
      writer.putBxReg('lr');
      writer.flush();
    } else if (arch === 'x64' || arch === 'x86') {
      code.writeU8(0xc3);
    } else {
      throw new Error('unsupported arch: ' + arch);
    }
  });
}

function writeNopRet(address, arch) {
  if (arch !== 'arm64') {
    writeReturn(address, arch);
    return;
  }
  Memory.patchCode(address, 16, function (code) {
    const writer = new Arm64Writer(code, { pc: address });
    writer.putNop();
    writer.putRet();
    writer.flush();
  });
}

function applyOffsetPatches() {
  const base = moduleBase();
  if (base === null) {
    return false;
  }
  for (const item of TARGET_OFFSETS) {
    if (!item.offset) {
      continue;
    }
    const address = base.add(ptr(item.offset));
    if (item.patch === 'ret') {
      writeReturn(address, item.arch || Process.arch);
      log('patched ' + item.name + ' at ' + TARGET_LIB + '!' + item.offset.toString(16) + ' => ' + address);
    }
  }
  return true;
}

function patchDetectionThreadStart(start, reason) {
  const mod = Process.findModuleByName(TARGET_LIB);
  if (mod === null || ptr(start).compare(mod.base) < 0 || ptr(start).compare(mod.base.add(mod.size)) >= 0) {
    return false;
  }
  const off = ptr(start).sub(mod.base).toUInt32();
  const hit = DETECTION_THREAD_OFFSETS.find(function (item) {
    return item.offset === off;
  });
  if (!hit) {
    log('thread start observed ' + TARGET_LIB + '!' + ptr(off));
    return false;
  }
  try {
    if ((hit.action || 'ret') === 'nopret') {
      writeNopRet(start, hit.arch || Process.arch);
    } else {
      writeReturn(start, hit.arch || Process.arch);
    }
    log('patched detection thread ' + TARGET_LIB + '!' + ptr(off) + ' reason=' + (hit.reason || reason || ''));
    return true;
  } catch (e) {
    log('patch detection thread failed ' + TARGET_LIB + '!' + ptr(off) + ': ' + e);
    return false;
  }
}

function hookDlopenForPatch() {
  ['android_dlopen_ext', 'dlopen'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) {
      return;
    }
    Interceptor.attach(fn, {
      onEnter(args) {
        this.path = args[0].isNull() ? '' : args[0].readCString();
      },
      onLeave() {
        if (this.path.indexOf(TARGET_LIB) !== -1) {
          log(name + ' loaded ' + this.path);
          setTimeout(applyOffsetPatches, 0);
        }
      },
    });
    log('hooked ' + name);
  });
}

function shouldHide(text) {
  if (!text) {
    return false;
  }
  const lower = text.toLowerCase();
  return HIDE_KEYWORDS.some(function (keyword) {
    return lower.indexOf(keyword.toLowerCase()) !== -1;
  });
}

function shouldHidePath(text) {
  if (!text) {
    return false;
  }
  const lower = text.toLowerCase();
  return ROOT_PATHS.some(function (item) {
    const needle = item.toLowerCase();
    return lower === needle || lower.indexOf(needle) !== -1;
  }) || shouldHide(text);
}

function hookStringChecks() {
  ['strstr', 'strcasestr'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) {
      return;
    }
    Interceptor.attach(fn, {
      onEnter(args) {
        this.hide = false;
        const haystack = args[0].isNull() ? '' : args[0].readCString();
        const needle = args[1].isNull() ? '' : args[1].readCString();
        if (shouldHide(haystack) || shouldHide(needle)) {
          this.hide = true;
        }
      },
      onLeave(retval) {
        if (this.hide && !retval.isNull()) {
          retval.replace(ptr(0));
        }
      },
    });
    log('hooked ' + name);
  });
}

function hookProcOpen() {
  ['open', 'openat'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) {
      return;
    }
    Interceptor.attach(fn, {
      onEnter(args) {
        const pathArg = name === 'open' ? args[0] : args[1];
        const path = pathArg.isNull() ? '' : pathArg.readCString();
        this.hide = shouldHidePath(path);
        if (path.indexOf('/proc/self/maps') !== -1 || path.indexOf('/proc/self/status') !== -1) {
          log(name + ' ' + path);
        }
      },
      onLeave(retval) {
        if (this.hide) {
          retval.replace(ptr(-1));
        }
      },
    });
    log('hooked ' + name);
  });
}

function hookRootPathChecks() {
  [
    ['access', 0],
    ['faccessat', 1],
    ['stat', 0],
    ['lstat', 0],
    ['__stat', 0],
    ['__lstat', 0],
    ['readlink', 0],
    ['readlinkat', 1],
    ['fopen', 0],
  ].forEach(function (spec) {
    const name = spec[0];
    const idx = spec[1];
    const fn = Module.findExportByName(null, name);
    if (fn === null) return;
    Interceptor.attach(fn, {
      onEnter(args) {
        this.path = args[idx].isNull() ? '' : args[idx].readCString();
        this.hide = shouldHidePath(this.path);
      },
      onLeave(retval) {
        if (this.hide) {
          log(name + ' hide ' + this.path);
          retval.replace(name === 'fopen' ? ptr(0) : ptr(-1));
        }
      },
    });
    log('hooked ' + name + ' root/path hiding');
  });
}

function hookSystemProperties() {
  const propGet = Module.findExportByName('libc.so', '__system_property_get');
  if (propGet === null) return;
  Interceptor.attach(propGet, {
    onEnter(args) {
      this.name = args[0].isNull() ? '' : args[0].readCString();
      this.value = args[1];
    },
    onLeave(retval) {
      let replacement = null;
      if (this.name === 'ro.debuggable') replacement = '0';
      else if (this.name === 'ro.secure') replacement = '1';
      else if (this.name === 'ro.build.tags') replacement = 'release-keys';
      else if (/magisk|zygisk|frida|florida|xposed|lsposed|kernelsu|ksu/i.test(this.name)) replacement = '';
      if (replacement === null) return;
      try {
        this.value.writeUtf8String(replacement);
        retval.replace(ptr(replacement.length));
        log('property ' + this.name + ' -> ' + replacement);
      } catch (_) {
      }
    },
  });
  log('hooked __system_property_get');
}

function hookProcReadFiltering() {
  const fdPaths = {};
  ['open', 'openat'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) return;
    Interceptor.attach(fn, {
      onEnter(args) {
        const pathArg = name === 'open' ? args[0] : args[1];
        this.path = pathArg.isNull() ? '' : pathArg.readCString();
      },
      onLeave(retval) {
        if (retval.toInt32() >= 0 && this.path) {
          fdPaths[retval.toInt32()] = this.path;
        }
      },
    });
  });

  const close = Module.findExportByName(null, 'close');
  if (close !== null) {
    Interceptor.attach(close, {
      onEnter(args) { this.fd = args[0].toInt32(); },
      onLeave() { delete fdPaths[this.fd]; },
    });
  }

  const read = Module.findExportByName(null, 'read');
  if (read === null) return;
  Interceptor.attach(read, {
    onEnter(args) {
      this.fd = args[0].toInt32();
      this.buf = args[1];
      const path = fdPaths[this.fd] || '';
      this.filter = /^\/proc\//.test(path) && /(maps|status|cmdline|task|stat|comm|environ)/.test(path);
    },
    onLeave(retval) {
      if (!this.filter) return;
      const n = retval.toInt32();
      if (n <= 0 || n > 0x10000) return;
      try {
        const oldText = this.buf.readUtf8String(n);
        let newText = oldText.replace(/TracerPid:\s*\d+/g, 'TracerPid:\t0');
        HIDE_KEYWORDS.forEach(function (keyword) {
          const re = new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
          newText = newText.replace(re, keyword[0] + '***');
        });
        if (newText !== oldText) {
          if (newText.length > oldText.length) newText = newText.slice(0, oldText.length);
          while (newText.length < oldText.length) newText += '\n';
          this.buf.writeUtf8String(newText.slice(0, Math.max(0, n - 1)));
          log('filtered proc read fd=' + this.fd);
        }
      } catch (_) {
      }
    },
  });
  log('hooked proc read filtering');
}

function sockaddrPort(sockaddr) {
  try {
    const family = sockaddr.readU16();
    if (family !== 2) {
      return null;
    }
    return ((sockaddr.add(2).readU8() << 8) | sockaddr.add(3).readU8()) & 0xffff;
  } catch (err) {
    return null;
  }
}

function hookConnect() {
  const fn = Module.findExportByName(null, 'connect');
  if (fn === null) {
    return;
  }
  Interceptor.attach(fn, {
    onEnter(args) {
      const port = sockaddrPort(args[1]);
      this.block = port !== null && BLOCK_PORTS.indexOf(port) !== -1;
      if (this.block) {
        log('blocking connect to suspected Frida port ' + port);
      }
    },
    onLeave(retval) {
      if (this.block) {
        retval.replace(ptr(-1));
      }
    },
  });
  log('hooked connect');
}

function hookPtraceAndExit() {
  const ptrace = Module.findExportByName(null, 'ptrace');
  if (ptrace !== null) {
    Interceptor.replace(ptrace, new NativeCallback(function () {
      log('ptrace blocked');
      return -1;
    }, 'long', ['int', 'int', 'pointer', 'pointer']));
    log('replaced ptrace');
  }

  ['exit', '_exit', 'abort', 'kill', 'tgkill', 'syscall'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) {
      return;
    }
    Interceptor.attach(fn, {
      onEnter(args) {
        log(name + ' called from ' + Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 4).join(' <- '));
      },
    });
    log('logging ' + name);
  });
}

function hookThreadStarts() {
  const pthreadCreate = Module.findExportByName('libc.so', 'pthread_create');
  if (pthreadCreate !== null) {
    Interceptor.attach(pthreadCreate, {
      onEnter(args) {
        patchDetectionThreadStart(args[2], 'pthread_create start_routine');
      },
    });
    log('hooked pthread_create thread start observer');
  }

  const clone = Module.findExportByName('libc.so', 'clone') || Module.findExportByName(null, 'clone');
  if (clone === null) return;
  Interceptor.attach(clone, {
    onEnter(args) {
      if (args[3].isNull()) return;
      try {
        const realStart = args[3].add(BIONIC_PTHREAD_START_OFFSET).readPointer();
        if (realStart.isNull()) return;
        patchDetectionThreadStart(realStart, 'clone pthread_struct +' + BIONIC_PTHREAD_START_OFFSET);
      } catch (e) {
        log('clone pthread start decode failed: ' + e);
      }
    },
  });
  log('hooked clone pthread_struct start observer');
}

setImmediate(function () {
  hookDlopenForPatch();
  hookStringChecks();
  hookProcOpen();
  hookRootPathChecks();
  hookSystemProperties();
  hookProcReadFiltering();
  hookConnect();
  hookPtraceAndExit();
  hookThreadStarts();
  setTimeout(applyOffsetPatches, 500);
});
