/*
 * Frida helper for authorized Android unpacking timing.
 * Logs native library loads and common dex/class-loader events.
 */

"use strict";

function log(message) {
  console.log("[dex-watch] " + message);
}

function hookJavaLoaders() {
  Java.perform(function () {
    var System = Java.use("java.lang.System");
    System.loadLibrary.overload("java.lang.String").implementation = function (name) {
      log("System.loadLibrary(" + name + ")");
      return this.loadLibrary(name);
    };
    System.load.overload("java.lang.String").implementation = function (path) {
      log("System.load(" + path + ")");
      return this.load(path);
    };

    var DexClassLoader = Java.use("dalvik.system.DexClassLoader");
    DexClassLoader.$init.implementation = function (dexPath, optimizedDirectory, librarySearchPath, parent) {
      log("DexClassLoader dexPath=" + dexPath + " opt=" + optimizedDirectory + " lib=" + librarySearchPath);
      return this.$init(dexPath, optimizedDirectory, librarySearchPath, parent);
    };

    try {
      var InMemoryDexClassLoader = Java.use("dalvik.system.InMemoryDexClassLoader");
      InMemoryDexClassLoader.$init.overloads.forEach(function (overload) {
        overload.implementation = function () {
          log("InMemoryDexClassLoader args=" + arguments.length);
          return overload.apply(this, arguments);
        };
      });
    } catch (err) {
      log("InMemoryDexClassLoader unavailable: " + err);
    }

    try {
      var DexFile = Java.use("dalvik.system.DexFile");
      DexFile.loadDex.implementation = function (sourcePathName, outputPathName, flags) {
        log("DexFile.loadDex src=" + sourcePathName + " out=" + outputPathName + " flags=" + flags);
        return this.loadDex(sourcePathName, outputPathName, flags);
      };
    } catch (err) {
      log("DexFile.loadDex hook unavailable: " + err);
    }
  });
}

function hookNativeLoaders() {
  ["android_dlopen_ext", "dlopen"].forEach(function (name) {
    var address = Module.findExportByName(null, name);
    if (!address) {
      return;
    }
    Interceptor.attach(address, {
      onEnter: function (args) {
        this.path = args[0].isNull() ? "" : args[0].readCString();
      },
      onLeave: function (retval) {
        if (this.path) {
          log(name + "(" + this.path + ") => " + retval);
        }
      },
    });
  });
}

setImmediate(function () {
  hookNativeLoaders();
  if (Java.available) {
    hookJavaLoaders();
  } else {
    log("Java runtime unavailable");
  }
});
