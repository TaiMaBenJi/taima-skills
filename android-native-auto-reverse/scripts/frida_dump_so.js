/*
 * Authorized Android loaded-SO dump template.
 *
 * Edit TARGET_LIB before use, then run for example:
 *   frida -U -f com.example.app -l frida_dump_so.js --no-pause
 *
 * The dump is raw mapped memory. Validate and fix it separately before IDA/Ghidra.
 */

'use strict';

const TARGET_LIB = 'libtarget.so';
const OUTPUT_DIR = '/data/local/tmp';

function sanitizeName(name) {
  return name.replace(/[^A-Za-z0-9_.-]/g, '_');
}

function dumpModule(moduleName) {
  const mod = Process.findModuleByName(moduleName);
  if (mod === null) {
    console.log('[dump_so] module not loaded: ' + moduleName);
    return false;
  }

  const outPath = OUTPUT_DIR + '/' + sanitizeName(moduleName) + '_' + mod.base + '_' + mod.size + '.dump.so';
  console.log('[dump_so] dumping ' + moduleName + ' base=' + mod.base + ' size=' + mod.size + ' path=' + mod.path);

  const bytes = mod.base.readByteArray(mod.size);
  const file = new File(outPath, 'wb');
  file.write(bytes);
  file.flush();
  file.close();

  console.log('[dump_so] wrote ' + outPath);
  return true;
}

function hookDlopen() {
  const names = ['android_dlopen_ext', 'dlopen'];
  for (const name of names) {
    const ptr = Module.findExportByName(null, name);
    if (ptr === null) continue;

    Interceptor.attach(ptr, {
      onEnter(args) {
        this.path = args[0].isNull() ? '' : args[0].readCString();
      },
      onLeave() {
        if (this.path && this.path.indexOf(TARGET_LIB) !== -1) {
          console.log('[dump_so] loader hit ' + name + ': ' + this.path);
          setTimeout(function () {
            dumpModule(TARGET_LIB);
          }, 100);
        }
      }
    });
    console.log('[dump_so] hooked ' + name);
  }
}

setImmediate(function () {
  hookDlopen();
  setTimeout(function () {
    dumpModule(TARGET_LIB);
  }, 1000);
});
