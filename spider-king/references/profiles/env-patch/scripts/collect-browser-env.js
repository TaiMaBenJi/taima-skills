/*
 * Browser-side environment collector.
 * Paste into DevTools Console/Snippets when a Node.js env rebuild needs real
 * browser seed values. It only reads local browser state and prints JSON; it
 * does not send data over the network.
 */
(function collectBrowserEnv() {
  const CONFIG = {
    cookieNames: [],
    localStorageKeys: [],
    sessionStorageKeys: [],
    includeCanvas: false,
  };

  function safeCall(fn, fallback) {
    try {
      return fn();
    } catch (err) {
      return fallback;
    }
  }

  function pickStorage(storage, keys) {
    const out = {};
    if (!storage) return out;
    for (const key of keys) {
      out[key] = safeCall(() => storage.getItem(key), null);
    }
    return out;
  }

  function pickCookies(names) {
    if (names.length === 0) return {};
    const wanted = new Set(names);
    const out = {};
    const pairs = safeCall(() => document.cookie.split(';'), []);
    for (const pair of pairs) {
      const separator = pair.indexOf('=');
      const name = (separator === -1 ? pair : pair.slice(0, separator)).trim();
      if (wanted.has(name)) out[name] = separator === -1 ? '' : pair.slice(separator + 1);
    }
    return out;
  }

  function dumpNavigator() {
    return {
      userAgent: safeCall(() => navigator.userAgent, ""),
      platform: safeCall(() => navigator.platform, ""),
      vendor: safeCall(() => navigator.vendor, ""),
      language: safeCall(() => navigator.language, ""),
      languages: safeCall(() => Array.from(navigator.languages || []), []),
      webdriver: safeCall(() => navigator.webdriver, undefined),
      hardwareConcurrency: safeCall(() => navigator.hardwareConcurrency, undefined),
      deviceMemory: safeCall(() => navigator.deviceMemory, undefined),
      maxTouchPoints: safeCall(() => navigator.maxTouchPoints, undefined),
      cookieEnabled: safeCall(() => navigator.cookieEnabled, undefined),
      pdfViewerEnabled: safeCall(() => navigator.pdfViewerEnabled, undefined),
      userAgentData: safeCall(() => navigator.userAgentData ? JSON.parse(JSON.stringify(navigator.userAgentData)) : null, null),
      connection: safeCall(() => navigator.connection ? JSON.parse(JSON.stringify(navigator.connection)) : null, null),
    };
  }

  function dumpDocument() {
    return {
      origin: safeCall(() => location.origin, ""),
      compatMode: safeCall(() => document.compatMode, ""),
      dir: safeCall(() => document.dir, ""),
      title: safeCall(() => document.title, ""),
      designMode: safeCall(() => document.designMode, ""),
      readyState: safeCall(() => document.readyState, ""),
      contentType: safeCall(() => document.contentType, ""),
      inputEncoding: safeCall(() => document.inputEncoding, ""),
      domain: safeCall(() => document.domain, ""),
      characterSet: safeCall(() => document.characterSet, ""),
      charset: safeCall(() => document.charset, ""),
      hidden: safeCall(() => document.hidden, undefined),
    };
  }

  function collectCanvasFingerprint() {
    return safeCall(() => {
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) return { canvas2d: null, webgl: null };
      ctx.textBaseline = "top";
      ctx.font = "14px Arial";
      ctx.fillStyle = "#f60";
      ctx.fillRect(10, 10, 120, 40);
      ctx.fillStyle = "#069";
      ctx.fillText("env-patch", 14, 16);

      const canvas2d = safeCall(() => canvas.toDataURL(), null);
      const gl = safeCall(() => canvas.getContext("webgl") || canvas.getContext("experimental-webgl"), null);
      const webgl = gl ? {
        vendor: safeCall(() => gl.getParameter(37445), null),
        renderer: safeCall(() => gl.getParameter(37446), null),
      } : null;
      return { canvas2d, webgl };
    }, { canvas2d: null, webgl: null });
  }

  const payload = {
    timestamp: new Date().toISOString(),
    config: {
      cookieNames: CONFIG.cookieNames.slice(),
      localStorageKeys: CONFIG.localStorageKeys.slice(),
      sessionStorageKeys: CONFIG.sessionStorageKeys.slice(),
      includeCanvas: CONFIG.includeCanvas,
    },
    location: {
      origin: safeCall(() => location.origin, ""),
      protocol: safeCall(() => location.protocol, ""),
      host: safeCall(() => location.host, ""),
      hostname: safeCall(() => location.hostname, ""),
      pathname: safeCall(() => location.pathname, ""),
      searchLength: safeCall(() => location.search.length, 0),
      hashLength: safeCall(() => location.hash.length, 0),
    },
    history: {
      length: safeCall(() => history.length, undefined),
      scrollRestoration: safeCall(() => history.scrollRestoration, undefined),
    },
    navigator: dumpNavigator(),
    document: dumpDocument(),
    screen: safeCall(() => ({
      width: screen.width,
      height: screen.height,
      availWidth: screen.availWidth,
      availHeight: screen.availHeight,
      availLeft: screen.availLeft,
      availTop: screen.availTop,
      colorDepth: screen.colorDepth,
      pixelDepth: screen.pixelDepth,
      orientation: screen.orientation,
    }), {}),
    windowMetrics: safeCall(() => ({
      devicePixelRatio: window.devicePixelRatio,
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      outerWidth: window.outerWidth,
      outerHeight: window.outerHeight,
      isSecureContext: window.isSecureContext,
    }), {}),
    cookies: pickCookies(CONFIG.cookieNames),
    localStorage: pickStorage(window.localStorage, CONFIG.localStorageKeys),
    sessionStorage: pickStorage(window.sessionStorage, CONFIG.sessionStorageKeys),
    fingerprint: CONFIG.includeCanvas ? collectCanvasFingerprint() : null,
  };

  console.log(JSON.stringify(payload, null, 2));
  return payload;
})();
