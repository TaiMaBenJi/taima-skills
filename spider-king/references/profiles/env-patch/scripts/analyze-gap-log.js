import { fileURLToPath } from "node:url";

const MODULE_PRIORITY = [
  "prototype-builder",
  "descriptor-guard",
  "native-protector",
  "navigator-module",
  "document-module",
  "document-all-module",
  "storage-module",
  "fingerprint-module",
  "performance-module",
  "crypto-module",
  "audio-fingerprint-module",
  "webrtc-module",
  "worker-module",
  "stack-clean-module",
];

function toArray(value) {
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.logs)) return value.logs;
  return [];
}

function unique(values) {
  return Array.from(new Set(values));
}

function extractPathList(input, key, type) {
  if (Array.isArray(input[key])) return unique(input[key]);
  return unique(
    toArray(input)
      .filter((item) => item && item.type === type && typeof item.path === "string")
      .map((item) => item.path),
  );
}

function inferModulesFromPath(path) {
  const modules = [];
  const value = String(path || "");

  if (/__proto__|prototype|constructor/.test(value)) modules.push("prototype-builder");
  if (/getOwnPropertyDescriptor|defineProperty|descriptor|ownKeys/.test(value)) modules.push("descriptor-guard");
  if (/toString|name|length|caller|arguments/.test(value)) modules.push("native-protector");
  if (/navigator|plugins|mimeTypes|webdriver|getBattery|userAgentData/.test(value)) {
    modules.push("navigator-module");
    if (/getBattery/.test(value)) modules.push("fingerprint-module");
  }
  if (/document\.all/.test(value)) {
    modules.push("document-all-module");
    modules.push("document-module");
  } else if (/document|createElement|querySelector|cookie/.test(value)) {
    modules.push("document-module");
  }
  if (/localStorage|sessionStorage|indexedDB|cookieStore/.test(value)) modules.push("storage-module");
  if (/canvas|webgl|screen|devicePixelRatio|getContext|toDataURL/.test(value)) modules.push("fingerprint-module");
  if (/performance|Performance/.test(value)) modules.push("performance-module");
  if (/crypto|msCrypto|getRandomValues|subtle/.test(value)) modules.push("crypto-module");
  if (/AudioContext|OfflineAudioContext|Oscillator|Analyser/.test(value)) modules.push("audio-fingerprint-module");
  if (/RTCPeerConnection|RTCDataChannel|RTCIceCandidate|RTCSessionDescription/.test(value)) modules.push("webrtc-module");
  if (/Worker|SharedWorker|MessagePort|BroadcastChannel/.test(value)) modules.push("worker-module");
  if (/Error|stack|prepareStackTrace/.test(value)) modules.push("stack-clean-module");

  return unique(modules);
}

function scoreEvidence(entry) {
  if (!entry || !entry.type) return 0;
  if (entry.type === "invoke-error") return 5;
  if (entry.type === "missing") return 4;
  if (entry.type === "descriptor" || entry.type === "prototype") return 3;
  return 1;
}

export function analyzeGapLog(input = {}) {
  const logs = toArray(input);
  const missingPaths = extractPathList(input, "missingPaths", "missing");
  const descriptorAccess = extractPathList(input, "descriptorAccess", "descriptor");
  const prototypeAccess = extractPathList(input, "prototypeAccess", "prototype");
  const invocationErrors = extractPathList(input, "invocationErrors", "invoke-error");
  const groupedByModule = Object.create(null);

  for (const entry of logs) {
    const modules = inferModulesFromPath(entry.path);
    if (!modules.length) continue;
    for (const moduleName of modules) {
      if (!groupedByModule[moduleName]) {
        groupedByModule[moduleName] = { score: 0, evidence: [] };
      }
      groupedByModule[moduleName].score += scoreEvidence(entry);
      groupedByModule[moduleName].evidence.push(entry);
    }
  }

  const recommendedModules = Object.keys(groupedByModule).sort((left, right) => {
    const leftPriority = MODULE_PRIORITY.indexOf(left);
    const rightPriority = MODULE_PRIORITY.indexOf(right);
    const leftScore = groupedByModule[left].score;
    const rightScore = groupedByModule[right].score;
    if (rightScore !== leftScore) return rightScore - leftScore;
    return leftPriority - rightPriority;
  });

  const nextActions = [];
  if (recommendedModules.includes("prototype-builder")) {
    nextActions.push("先修复构造器、原型链和 instanceof 关系，再处理对象值。");
  }
  if (recommendedModules.includes("descriptor-guard")) {
    nextActions.push("把 getOwnPropertyDescriptor/defineProperty/propertyIsEnumerable 的结果对齐。");
  }
  if (recommendedModules.includes("native-protector")) {
    nextActions.push("统一接管 Function.prototype.toString，并补齐 getter/setter/name/length 保护。");
  }
  if (recommendedModules.includes("document-all-module")) {
    nextActions.push("单独评估 document.all，明确是 native-addon、V8 API 还是 fallback 路线。");
  }
  if (recommendedModules.includes("storage-module")) {
    nextActions.push("把 cookie/localStorage/sessionStorage 的真实状态同步进运行时。");
  }
  if (recommendedModules.includes("fingerprint-module")) {
    nextActions.push("把 canvas/webgl/screen/battery 等指纹点单独建模，不要和普通 navigator 属性混补。");
  }

  return {
    totalLogs: logs.length,
    missingPaths,
    descriptorAccess,
    prototypeAccess,
    invocationErrors,
    recommendedModules,
    groupedByModule,
    nextActions: unique(nextActions),
  };
}

export { inferModulesFromPath };

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const fs = await import("node:fs");
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error("Usage: node analyze-gap-log.js <gap-log.json>");
    process.exit(1);
  }
  const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  console.log(JSON.stringify(analyzeGapLog(input), null, 2));
}
