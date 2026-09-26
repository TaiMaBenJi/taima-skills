/*
 * Authorized Frida Stalker helper for OLLVM/native algorithm recovery.
 *
 * Edit TARGET_LIB and TARGET_OFFSETS in a task-local copy. The script follows
 * the current thread only while a target function is executing, then emits:
 * - call summary: callee offset -> count
 * - call/ret trace: caller offset -> target offset
 *
 * Use summary mode first to reduce noise; enable TRACE_CALL_RET only for the
 * narrowed window.
 */

'use strict';

const TARGET_LIB = 'libtarget.so';
const TARGET_OFFSETS = [
  // 0x23ad0,
];

const TRACE_CALL_RET = true;
const TRACE_EXEC_BLOCKS = false;
const MAX_TRACE_EVENTS = 20000;
const MAX_ARG_DUMP = 0x80;
const HOOK_SUMMARY_CALLEES = false;

const tracedThreads = {};
let traceEventCount = 0;

function log(message) {
  console.log('[stalker-ollvm] ' + message);
}

function moduleFor(address) {
  try {
    return Process.findModuleByAddress(ptr(address));
  } catch (_) {
    return null;
  }
}

function targetModule() {
  return Process.findModuleByName(TARGET_LIB);
}

function describe(address) {
  const mod = moduleFor(address);
  if (mod === null) return ptr(address) + ' <no-module>';
  return mod.name + '!' + ptr(address).sub(mod.base) + ' ' + ptr(address);
}

function isInTarget(address) {
  const mod = targetModule();
  if (mod === null) return false;
  const p = ptr(address);
  return p.compare(mod.base) >= 0 && p.compare(mod.base.add(mod.size)) < 0;
}

function hexdumpArg(value) {
  try {
    const p = ptr(value);
    const range = Process.findRangeByAddress(p);
    if (range === null) return p.toString();
    return hexdump(p, { length: Math.min(MAX_ARG_DUMP, range.base.add(range.size).sub(p).toInt32()), ansi: false });
  } catch (_) {
    return ptr(value).toString();
  }
}

function printArgs(args) {
  for (let i = 0; i < 6; i += 1) {
    log('arg' + i + '=' + hexdumpArg(args[i]));
  }
}

function hookNativeAddr(address) {
  Interceptor.attach(address, {
    onEnter(args) {
      log('enter ' + describe(address));
      printArgs(args);
      const tid = Process.getCurrentThreadId();
      tracedThreads[tid] = true;
      traceEventCount = 0;
      Stalker.follow(tid, {
        events: {
          call: true,
          ret: TRACE_CALL_RET,
          exec: TRACE_EXEC_BLOCKS,
          block: TRACE_EXEC_BLOCKS,
          compile: false,
        },
        onCallSummary(summary) {
          const rows = [];
          Object.keys(summary).forEach(function (addr) {
            if (!isInTarget(addr)) return;
            const mod = moduleFor(addr);
            rows.push({
              offset: ptr(addr).sub(mod.base).toString(),
              address: ptr(addr).toString(),
              count: summary[addr],
            });
          });
          rows.sort(function (a, b) { return b.count - a.count; });
          rows.forEach(function (row) {
            log('summary callee=' + TARGET_LIB + '!' + row.offset + ' count=' + row.count + ' addr=' + row.address);
            if (HOOK_SUMMARY_CALLEES) {
              tryHookSummaryCallee(ptr(row.address));
            }
          });
        },
        onReceive(events) {
          if (!TRACE_CALL_RET && !TRACE_EXEC_BLOCKS) return;
          const parsed = Stalker.parse(events);
          for (let i = 0; i < parsed.length; i += 1) {
            if (traceEventCount >= MAX_TRACE_EVENTS) return;
            const ev = parsed[i];
            const type = ev[0];
            const from = ptr(ev[1]);
            const to = ptr(ev[2]);
            if (!isInTarget(from) && !isInTarget(to)) continue;
            traceEventCount += 1;
            log('event ' + type + ' from=' + describe(from) + ' to=' + describe(to));
          }
        },
      });
    },
    onLeave(retval) {
      const tid = Process.getCurrentThreadId();
      log('leave ' + describe(address) + ' retval=' + hexdumpArg(retval));
      if (tracedThreads[tid]) {
        Stalker.unfollow(tid);
        Stalker.garbageCollect();
        delete tracedThreads[tid];
      }
    },
  });
}

function tryHookSummaryCallee(address) {
  if (!isInTarget(address)) return;
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        log('callee enter ' + describe(address));
        printArgs(args);
        log('backtrace ' + Thread.backtrace(this.context, Backtracer.ACCURATE).map(describe).join(' <- '));
      },
      onLeave(retval) {
        log('callee leave ' + describe(address) + ' retval=' + hexdumpArg(retval));
      },
    });
  } catch (_) {
  }
}

function install() {
  const mod = targetModule();
  if (mod === null) {
    log('target module not loaded: ' + TARGET_LIB);
    return;
  }
  TARGET_OFFSETS.forEach(function (off) {
    if (!off) return;
    const address = mod.base.add(ptr(off));
    log('hook target ' + TARGET_LIB + '!' + ptr(off) + ' @ ' + address);
    hookNativeAddr(address);
  });
}

function hookDlopen() {
  ['android_dlopen_ext', 'dlopen'].forEach(function (name) {
    const fn = Module.findExportByName(null, name);
    if (fn === null) return;
    Interceptor.attach(fn, {
      onEnter(args) {
        this.path = args[0].isNull() ? '' : args[0].readCString();
      },
      onLeave() {
        if (this.path.indexOf(TARGET_LIB) !== -1) {
          log(name + ' loaded ' + this.path);
          setTimeout(install, 0);
        }
      },
    });
  });
}

setImmediate(function () {
  log('starting pid=' + Process.id + ' arch=' + Process.arch + ' target=' + TARGET_LIB);
  hookDlopen();
  install();
});
