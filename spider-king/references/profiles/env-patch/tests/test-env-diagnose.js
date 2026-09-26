import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';


const profileDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const diagnose = path.join(profileDir, 'scripts', 'env-diagnose.js');
const envCoreUrl = new URL('../scripts/env_core.js', import.meta.url).href;
const collectorSource = fs.readFileSync(path.join(profileDir, 'scripts', 'collect-browser-env.js'), 'utf8');
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'env-profile-'));

try {
  assert.match(collectorSource, /cookieNames:\s*\[\]/);
  assert.match(collectorSource, /localStorageKeys:\s*\[\]/);
  assert.match(collectorSource, /sessionStorageKeys:\s*\[\]/);
  assert.match(collectorSource, /includeCanvas:\s*false/);
  assert.doesNotMatch(collectorSource, /storage\.length/);

  fs.writeFileSync(path.join(tempDir, 'custom-patch.js'), 'globalThis.__fixtureValue = 42;\n');
  fs.writeFileSync(
    path.join(tempDir, 'target.js'),
    'if (globalThis.__fixtureValue !== 42) throw new Error("custom patch missing");\n',
  );

  const refused = spawnSync(
    process.execPath,
    [diagnose, '--quiet', 'target.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(refused.status, 2);
  assert.match(JSON.parse(refused.stdout).error, /not a security boundary/);

  const success = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', '--env', 'custom-patch.js', 'target.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(success.status, 0, success.stderr || success.stdout);
  assert.equal(JSON.parse(success.stdout).success, true);

  const missing = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', '--env', 'missing-patch.js', 'target.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.notEqual(missing.status, 0);
  const missingResult = JSON.parse(missing.stdout);
  assert.equal(missingResult.success, false);
  assert.match(missingResult.error, /env module not found/);

  fs.writeFileSync(
    path.join(tempDir, 'secret-output.js'),
    'console.log("TOKEN_LEAK_PROBE");\n' +
      'console.log({ cookie: "COOKIE_LEAK_PROBE" });\n' +
      'throw new Error("KEY_LEAK_PROBE");\n',
  );
  const secretOutput = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', 'secret-output.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.notEqual(secretOutput.status, 0);
  assert.doesNotMatch(secretOutput.stdout, /TOKEN_LEAK_PROBE|COOKIE_LEAK_PROBE|KEY_LEAK_PROBE/);
  const secretOutputResult = JSON.parse(secretOutput.stdout);
  assert.match(secretOutputResult.error, /details redacted/);
  assert.deepEqual(secretOutputResult.consoleOutput, [
    ['log', '[String length=16]'],
    ['log', '[Object]'],
  ]);

  fs.writeFileSync(
    path.join(tempDir, 'console-observer.js'),
    'let observed = 0;\n' +
      'const value = { toString() { observed += 1; throw new Error("observer ran"); } };\n' +
      'console.log(value);\n' +
      'if (observed !== 0) throw new Error("console observer changed behavior");\n',
  );
  const consoleObserver = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', 'console-observer.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(consoleObserver.status, 0, consoleObserver.stderr || consoleObserver.stdout);
  assert.deepEqual(JSON.parse(consoleObserver.stdout).consoleOutput, [['log', '[Object]']]);

  fs.writeFileSync(
    path.join(tempDir, 'escape-probe.js'),
    'const viaAtob = atob.constructor("return typeof process")();\n' +
      'const viaConsole = console.log.constructor("return typeof process")();\n' +
      'if (viaAtob !== "undefined" || viaConsole !== "undefined") throw new Error("host process escaped");\n',
  );
  const escapeProbe = spawnSync(
    process.execPath,
    [diagnose, '--quiet', '--external-sandbox-confirmed', 'escape-probe.js'],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(escapeProbe.status, 0, escapeProbe.stderr || escapeProbe.stdout);

  const lifecycleProbe = `
    import assert from 'node:assert/strict';
    import nodeProcess from 'node:process';
    const before = Function.prototype.toString;
    const env = (await import(${JSON.stringify(envCoreUrl)})).default;
    assert.equal(Function.prototype.toString, before);
    delete nodeProcess.env.SPIDER_EXTERNAL_SANDBOX_CONFIRMED;
    assert.throws(() => env.init({}), /external disposable sandbox/);
    nodeProcess.env.SPIDER_EXTERNAL_SANDBOX_CONFIRMED = '1';
    env.init({});
    assert.notEqual(Function.prototype.toString, before);
    assert.equal(globalThis.process, undefined);
    env.restore();
    assert.equal(Function.prototype.toString, before);
    assert.equal(globalThis.process, nodeProcess);
    delete nodeProcess.env.SPIDER_EXTERNAL_SANDBOX_CONFIRMED;
  `;
  const lifecycle = spawnSync(
    process.execPath,
    ['--input-type=module', '-e', lifecycleProbe],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(lifecycle.status, 0, lifecycle.stderr || lifecycle.stdout);

  const reportPrivacyProbe = `
    import assert from 'node:assert/strict';
    const env = (await import(${JSON.stringify(envCoreUrl)})).default;
    const tokenSecret = 'TOKEN_LEAK_PROBE_REPORT';
    const errorSecret = 'ERROR_LEAK_PROBE_REPORT';
    const numericSecret = 161803398874989;
    env.reset();
    const proxy = env.createProxy({
      invoke(text, number) {
        throw new Error(errorSecret);
      }
    }, 'fixture');
    try { proxy.invoke(tokenSecret, numericSecret); } catch (_) {}

    const consoleLines = [];
    const originalLog = console.log;
    let report;
    try {
      console.log = (...args) => { consoleLines.push(args); };
      report = env.report();
    } finally {
      console.log = originalLog;
      env.reset();
    }

    const dump = JSON.stringify({ report, consoleLines });
    assert.doesNotMatch(dump, /TOKEN_LEAK_PROBE_REPORT|ERROR_LEAK_PROBE_REPORT|161803398874989/);
    assert.match(dump, /String length=/);
    assert.match(dump, /\\[Number\\]/);
    assert.match(dump, /messageLength=/);
  `;
  const reportPrivacy = spawnSync(
    process.execPath,
    ['--input-type=module', '-e', reportPrivacyProbe],
    { cwd: tempDir, encoding: 'utf8' },
  );
  assert.equal(reportPrivacy.status, 0, reportPrivacy.stderr || reportPrivacy.stdout);

  console.log('env-diagnose profile tests: ok');
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
