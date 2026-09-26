/*
 * Authorized Android pthread/clone thread-start tracer.
 *
 * Purpose:
 * - Log pthread_create and clone thread starts.
 * - Recover the real pthread start routine from clone args[3] + 0x60 on
 *   Android/Bionic layouts where pthread_create only exposes a wrapper.
 * - Optionally patch known module offsets to RET after evidence is collected.
 *
 * Copy this file into the task workspace and edit PATCH_TARGETS for the sample.
 */

'use strict';

const PATCH_TARGETS = [
  // { module: 'libDexHelper.so', offset: 0x0, arch: 'arm64', reason: 'confirmed detection thread' },
  // { module: 'libmsaoaidsec.so', offset: 0x0, arch: 'arm64', reason: 'confirmed OAID/security worker' },
];

const INTERESTING_MODULES = [
  'libDexHelper',
  'libSecShell',
  'libsecexe',
  'libsecmain',
  'libmsaoaidsec',
  'libjiagu',
  'libshell',
  'libprotect',
];

function log(message) {
  console.log('[thread-trace] ' + message);
}

function moduleFor(address) {
  try {
    return Process.findModuleByAddress(address);
  } catch (_) {
    return null;
  }
}

function offsetOf(address, module) {
  return ptr(address).sub(module.base);
}

function isInterestingModule(name) {
  if (!name) return false;
  return INTERESTING_MODULES.some(function (needle) {
    return name.indexOf(needle) !== -1;
  });
}

function describeAddress(address) {
  if (!address || ptr(address).isNull()) {
    return 'null';
  }
  const mod = moduleFor(ptr(address));
  if (mod === null) {
    return address + ' <no-module>';
  }
  return mod.name + '!' + offsetOf(ptr(address), mod) + ' ' + address;
}

function patchRet(address, arch) {
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

function applyPatchTargets() {
  PATCH_TARGETS.forEach(function (target) {
    if (!target.offset) return;
    const mod = Process.findModuleByName(target.module);
    if (mod === null) return;
    const address = mod.base.add(ptr(target.offset));
    try {
      patchRet(address, target.arch || Process.arch);
      log('patched ' + target.module + '!' + ptr(target.offset) + ' at ' + address + ' reason=' + (target.reason || ''));
    } catch (e) {
      log('patch failed ' + target.module + '!' + ptr(target.offset) + ': ' + e);
    }
  });
}

function hookDlopenForPatchTiming() {
  ['android_dlopen_ext', 'dlopen'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) return;
    Interceptor.attach(fn, {
      onEnter(args) {
        this.path = args[0].isNull() ? '' : args[0].readCString();
      },
      onLeave() {
        if (this.path) {
          log(name + ' ' + this.path);
          setTimeout(applyPatchTargets, 0);
        }
      },
    });
    log('hooked ' + name);
  });
}

function hookPthreadCreate() {
  const fn = Module.findExportByName('libc.so', 'pthread_create');
  if (fn === null) {
    log('pthread_create not found');
    return;
  }
  Interceptor.attach(fn, {
    onEnter(args) {
      const start = args[2];
      const mod = moduleFor(start);
      if (mod !== null && (isInterestingModule(mod.name) || mod.name.indexOf('.so') !== -1)) {
        log('pthread_create start=' + describeAddress(start));
      }
    },
  });
  log('hooked pthread_create');
}

function hookClone() {
  const fn = Module.findExportByName('libc.so', 'clone') || Module.findExportByName(null, 'clone');
  if (fn === null) {
    log('clone not found');
    return;
  }
  Interceptor.attach(fn, {
    onEnter(args) {
      const wrapper = args[0];
      if (!wrapper.isNull()) {
        const wrapperMod = moduleFor(wrapper);
        if (wrapperMod !== null && isInterestingModule(wrapperMod.name)) {
          log('clone wrapper=' + describeAddress(wrapper));
        }
      }

      if (args[3].isNull()) {
        return;
      }

      try {
        const realStart = args[3].add(0x60).readPointer();
        if (realStart.isNull()) {
          return;
        }
        const realMod = moduleFor(realStart);
        if (realMod !== null) {
          const desc = describeAddress(realStart);
          if (isInterestingModule(realMod.name)) {
            log('clone real_start=' + desc + ' pthread_arg=' + args[3]);
            log('backtrace ' + Thread.backtrace(this.context, Backtracer.ACCURATE)
              .slice(0, 8)
              .map(DebugSymbol.fromAddress)
              .join(' <- '));
          } else {
            log('clone real_start=' + desc);
          }
        }
      } catch (e) {
        log('clone arg decode failed: ' + e);
      }
    },
  });
  log('hooked clone');
}

setImmediate(function () {
  log('starting pid=' + Process.id + ' arch=' + Process.arch);
  hookDlopenForPatchTiming();
  hookPthreadCreate();
  hookClone();
  setTimeout(applyPatchTargets, 300);
});
