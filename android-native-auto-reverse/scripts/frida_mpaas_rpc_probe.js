/*
 * Authorized mPaaS RPC request/response probe.
 *
 * Purpose:
 * - Locate and observe mPaaS RPC plaintext before transport encryption/signing.
 * - Hook Serializer.packet() for request bodies before HttpCaller integrity work.
 * - Hook HttpCaller/RpcInvoker response objects for response body evidence.
 *
 * Default mode is observe-only. Set ENABLE_BLOCKING_EDIT to true only in an
 * authorized lab with a controller that replies to Frida messages.
 */

'use strict';

const CFG = {
  enableBlockingEdit: false,
  editTimeoutMs: 15000,
  maxTextLog: 1200,
  serializerClasses: [
    'com.alipay.mobile.common.rpc.protocol.json.JsonSerializerV2',
    'com.alipay.mobile.common.rpc.protocol.json.SignJsonSerializer',
    'com.alipay.mobile.common.rpc.protocol.json.SimpleRpcJsonSerializerV2',
    'com.alipay.mobile.common.rpc.protocol.protobuf.PBSerializer',
    'com.alipay.mobile.common.rpc.protocol.protobuf.SimpleRpcPBSerializer',
  ],
  httpCallerClass: 'com.alipay.mobile.common.rpc.transport.http.HttpCaller',
  rpcInvokerClass: 'com.alipay.mobile.common.rpc.RpcInvoker',
  httpRequestClass: 'com.alipay.mobile.common.transport.http.HttpUrlRequest',
};

let JavaString = null;
let AtomicInteger = null;
let requestSeq = null;
const threadRequestIds = {};

function log(line) {
  console.log('[mpaas-rpc] ' + line);
}

function nextId(prefix) {
  try {
    return prefix + '-' + requestSeq.incrementAndGet();
  } catch (_) {
    return prefix + '-' + Date.now() + '-' + Math.floor(Math.random() * 100000);
  }
}

function currentThreadKey() {
  try {
    return Java.use('java.lang.Thread').currentThread().getId().toString();
  } catch (_) {
    return 'unknown-thread';
  }
}

function bytesToText(bytes) {
  if (bytes === null || bytes === undefined) return '';
  try {
    return JavaString.$new(bytes, 'UTF-8').toString();
  } catch (_) {
    try {
      return JavaString.$new(bytes).toString();
    } catch (_) {
      return '<non-utf8-bytes len=' + bytes.length + '>';
    }
  }
}

function textToBytes(text) {
  return JavaString.$new(text).getBytes('UTF-8');
}

function compact(text) {
  if (text === null || text === undefined) return '';
  const value = String(text);
  if (value.length <= CFG.maxTextLog) return value;
  return value.slice(0, CFG.maxTextLog) + '...<truncated len=' + value.length + '>';
}

function sendAndMaybeEdit(kind, id, body, meta) {
  send({ kind: kind, id: id, body: body, meta: meta || {} });
  if (!CFG.enableBlockingEdit) return null;

  let edited = null;
  let matched = false;
  recv(function (message) {
    if (!message || message.id !== id) return;
    if (message.kind === 'edit-' + kind || message.type === 'edit-' + kind) {
      edited = message.body !== undefined ? message.body : message.payload;
      matched = true;
    }
  }).wait(CFG.editTimeoutMs);
  return matched ? edited : null;
}

function hookSerializer(className) {
  let Klass = null;
  try {
    Klass = Java.use(className);
  } catch (_) {
    return false;
  }

  if (!Klass.packet) {
    log('no packet method on ' + className);
    return false;
  }

  Klass.packet.overloads.forEach(function (overload) {
    const ret = overload.returnType ? overload.returnType.name : '';
    if (ret !== '[B') return;

    overload.implementation = function () {
      const id = nextId('req');
      const threadKey = currentThreadKey();
      const originalBytes = overload.apply(this, arguments);
      const originalText = bytesToText(originalBytes);
      threadRequestIds[threadKey] = id;
      log(className + '.packet id=' + id + ' text=' + compact(originalText));

      const editedText = sendAndMaybeEdit('request', id, originalText, {
        className: className,
        thread: threadKey,
        note: 'Serializer.packet is before mPaaS HttpCaller transport integrity checks.',
      });

      if (editedText !== null && editedText !== originalText) {
        log('request edited id=' + id + ' oldLen=' + originalText.length + ' newLen=' + editedText.length);
        return textToBytes(editedText);
      }
      return originalBytes;
    };
    log('hooked ' + className + '.packet overload=' + overload.argumentTypes.map(t => t.name).join(','));
  });
  return true;
}

function callZeroArgStringMethod(obj, methodName) {
  try {
    if (obj && obj[methodName]) return String(obj[methodName]());
  } catch (_) {
  }
  return '';
}

function forEachJavaMethod(Klass, callback) {
  const names = {};
  try {
    if (Klass.$ownMembers) {
      Klass.$ownMembers.forEach(function (name) {
        if (name.indexOf('$') !== 0) names[name] = true;
      });
    }
  } catch (_) {
  }
  Object.keys(Klass).forEach(function (name) {
    if (name.indexOf('$') !== 0) names[name] = true;
  });

  Object.keys(names).forEach(function (methodName) {
    const member = Klass[methodName];
    if (member && member.overloads) callback(methodName, member);
  });
}

function tryGetReqData(requestObj) {
  try {
    if (requestObj && requestObj.getReqData) return bytesToText(requestObj.getReqData());
  } catch (_) {
  }
  return '';
}

function tryGetResData(responseObj) {
  try {
    if (responseObj && responseObj.getResData) return bytesToText(responseObj.getResData());
  } catch (_) {
  }
  return '';
}

function trySetResData(responseObj, body) {
  try {
    if (responseObj && responseObj.setResData) {
      responseObj.setResData(textToBytes(body));
      return true;
    }
  } catch (e) {
    log('setResData failed: ' + e);
  }
  return false;
}

function hookHttpCaller() {
  let HttpCaller = null;
  try {
    HttpCaller = Java.use(CFG.httpCallerClass);
  } catch (_) {
    log('HttpCaller not found: ' + CFG.httpCallerClass);
    return false;
  }

  forEachJavaMethod(HttpCaller, function (methodName, member) {
    member.overloads.forEach(function (overload) {
      const args = overload.argumentTypes.map(t => t.name);
      if (args.indexOf(CFG.httpRequestClass) === -1) return;

      overload.implementation = function () {
        const id = threadRequestIds[currentThreadKey()] || nextId('http');
        const requestArgIndex = args.indexOf(CFG.httpRequestClass);
        const requestObj = arguments[requestArgIndex];
        const reqData = tryGetReqData(requestObj);
        const url = callZeroArgStringMethod(requestObj, 'getUrl') || callZeroArgStringMethod(requestObj, 'getOriginUrl');

        send({ kind: 'transport-request', id: id, body: reqData, meta: { methodName: methodName, url: url } });
        log('HttpCaller.' + methodName + ' id=' + id + ' url=' + url + ' req=' + compact(reqData));

        const responseObj = overload.apply(this, arguments);
        const resData = tryGetResData(responseObj);
        log('HttpCaller.' + methodName + ' response id=' + id + ' text=' + compact(resData));

        const editedResp = sendAndMaybeEdit('response', id, resData, {
          className: CFG.httpCallerClass,
          methodName: methodName,
          url: url,
        });
        if (editedResp !== null && editedResp !== resData && trySetResData(responseObj, editedResp)) {
          log('response edited id=' + id);
        }
        return responseObj;
      };
      log('hooked ' + CFG.httpCallerClass + '.' + methodName + '(' + args.join(',') + ')');
    });
  });
  return true;
}

function hookRpcInvoker() {
  let RpcInvoker = null;
  try {
    RpcInvoker = Java.use(CFG.rpcInvokerClass);
  } catch (_) {
    log('RpcInvoker not found: ' + CFG.rpcInvokerClass);
    return false;
  }

  forEachJavaMethod(RpcInvoker, function (methodName, member) {
    member.overloads.forEach(function (overload) {
      const args = overload.argumentTypes.map(t => t.name);
      if (args.indexOf('[B') === -1) return;

      overload.implementation = function () {
        const id = threadRequestIds[currentThreadKey()] || nextId('rpc');
        const byteIndex = args.indexOf('[B');
        const packed = bytesToText(arguments[byteIndex]);
        log('RpcInvoker.' + methodName + ' id=' + id + ' packed=' + compact(packed));
        send({ kind: 'rpc-invoker', id: id, body: packed, meta: { methodName: methodName, args: args } });
        return overload.apply(this, arguments);
      };
      log('hooked ' + CFG.rpcInvokerClass + '.' + methodName + '(' + args.join(',') + ')');
    });
  });
  return true;
}

Java.perform(function () {
  JavaString = Java.use('java.lang.String');
  AtomicInteger = Java.use('java.util.concurrent.atomic.AtomicInteger');
  requestSeq = AtomicInteger.$new(0);

  log('starting pid=' + Process.id + ' edit=' + CFG.enableBlockingEdit);
  let serializerHits = 0;
  CFG.serializerClasses.forEach(function (className) {
    if (hookSerializer(className)) serializerHits += 1;
  });
  log('serializer classes hooked=' + serializerHits);
  hookRpcInvoker();
  hookHttpCaller();
});
