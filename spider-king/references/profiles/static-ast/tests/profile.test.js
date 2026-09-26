const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');

const profileDir = path.resolve(__dirname, '..');
const runner = path.join(profileDir, 'scripts', 'run-pipeline.js');
const fixtures = path.join(__dirname, 'fixtures');
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'spider-static-ast-'));

function run(input, name) {
  const output = path.join(tempDir, name);
  const result = spawnSync(process.execPath, [runner, input, output], { encoding: 'utf8', windowsHide: true });
  return { output, result };
}

try {
  const safe = run(path.join(fixtures, 'safe-sample.js'), 'safe');
  assert.equal(safe.result.status, 0, safe.result.stderr || safe.result.stdout);
  const safeReport = JSON.parse(fs.readFileSync(path.join(safe.output, 'pipeline-report.json'), 'utf8'));
  const safeDetection = JSON.parse(fs.readFileSync(path.join(safe.output, 'detection.json'), 'utf8'));
  const safeMetrics = JSON.parse(fs.readFileSync(path.join(safe.output, 'metrics.json'), 'utf8'));
  assert.equal(safeReport.targetCodeExecuted, false);
  assert.equal(safeReport.selectedPipeline, 'generic-static-safe');
  assert.equal(safeReport.steps.filter((step) => step.id === 'detect').length, 1);
  assert(safeReport.steps.every((step) => !Object.hasOwn(step, 'stdout')));
  assert.equal(safeDetection.metrics.computedMemberCount, 2);
  assert.equal(safeMetrics.metrics.computedMemberCount, 1);
  assert.equal(safeMetrics.metrics.dynamicExecutionCount, 0);
  assert.equal(safeDetection.hintProvided, false);
  assert.equal(Object.hasOwn(safeDetection, 'hint'), false);
  assert.match(fs.readFileSync(path.join(safe.output, 'final.js'), 'utf8'), /worker\.run\(1\)/);
  const originalContext = { globalThis: {} };
  const finalContext = { globalThis: {} };
  vm.createContext(originalContext);
  vm.createContext(finalContext);
  vm.runInContext(fs.readFileSync(path.join(fixtures, 'safe-sample.js'), 'utf8'), originalContext);
  vm.runInContext(fs.readFileSync(path.join(safe.output, 'final.js'), 'utf8'), finalContext);
  assert.equal(finalContext.globalThis.__staticAstResult, originalContext.globalThis.__staticAstResult);

  const hoistSensitive = run(path.join(fixtures, 'hoist-sensitive.js'), 'hoist-sensitive');
  assert.equal(hoistSensitive.result.status, 0, hoistSensitive.result.stderr || hoistSensitive.result.stdout);
  const hoistOriginalContext = { globalThis: {} };
  const hoistFinalContext = { globalThis: {} };
  vm.createContext(hoistOriginalContext);
  vm.createContext(hoistFinalContext);
  vm.runInContext(fs.readFileSync(path.join(fixtures, 'hoist-sensitive.js'), 'utf8'), hoistOriginalContext);
  const hoistFinalSource = fs.readFileSync(path.join(hoistSensitive.output, 'final.js'), 'utf8');
  vm.runInContext(hoistFinalSource, hoistFinalContext);
  assert.equal(hoistFinalContext.globalThis.__staticAstHoistState, hoistOriginalContext.globalThis.__staticAstHoistState);
  assert.match(hoistFinalSource, /if \(false\)/, 'Hoist-sensitive branch must remain intact');

  const ambiguous = run(path.join(fixtures, 'ambiguous-ob.js'), 'ambiguous');
  assert.equal(ambiguous.result.status, 0, ambiguous.result.stderr || ambiguous.result.stdout);
  const ambiguousDetection = JSON.parse(fs.readFileSync(path.join(ambiguous.output, 'detection.json'), 'utf8'));
  assert.equal(ambiguousDetection.selectedPipeline, 'generic-static-safe');
  assert.equal(ambiguousDetection.ambiguous, false);
  assert(ambiguousDetection.families.includes('hex-identifiers'));

  const sentinel = path.join(tempDir, 'target-code-executed.txt');
  const noExecuteInput = path.join(tempDir, 'must-not-execute.js');
  fs.writeFileSync(
    noExecuteInput,
    `require('node:fs').writeFileSync(${JSON.stringify(sentinel)}, 'executed');\n` +
      'globalThis.__mustNotRun = true;\n',
  );
  const noExecute = run(noExecuteInput, 'no-execute');
  assert.equal(noExecute.result.status, 0, noExecute.result.stderr || noExecute.result.stdout);
  assert.equal(fs.existsSync(sentinel), false, 'Static AST pipeline executed target source');
  const noExecuteReport = JSON.parse(fs.readFileSync(path.join(noExecute.output, 'pipeline-report.json'), 'utf8'));
  assert.equal(noExecuteReport.targetCodeExecuted, false);

  const invalid = run(path.join(fixtures, 'parse-error.js'), 'invalid');
  assert.equal(invalid.result.status, 2);
  const invalidReport = JSON.parse(fs.readFileSync(path.join(invalid.output, 'pipeline-report.json'), 'utf8'));
  assert.equal(invalidReport.status, 'failed');
  assert.equal(invalidReport.lastGoodFile, '00_source.js');
  assert.equal(invalidReport.targetCodeExecuted, false);
  assert.equal(fs.readFileSync(path.join(invalid.output, 'final.js'), 'utf8'), fs.readFileSync(path.join(fixtures, 'parse-error.js'), 'utf8'));

  const reusedOutput = path.join(tempDir, 'reused-output');
  const firstReuse = spawnSync(process.execPath, [runner, path.join(fixtures, 'safe-sample.js'), reusedOutput], { encoding: 'utf8', windowsHide: true });
  assert.equal(firstReuse.status, 0, firstReuse.stderr || firstReuse.stdout);
  assert.equal(fs.existsSync(path.join(reusedOutput, '01_safe_rewrite.js')), true);
  const failedReuse = spawnSync(process.execPath, [runner, path.join(fixtures, 'parse-error.js'), reusedOutput], { encoding: 'utf8', windowsHide: true });
  assert.equal(failedReuse.status, 2);
  assert.equal(fs.existsSync(path.join(reusedOutput, 'detection.json')), false);
  assert.equal(fs.existsSync(path.join(reusedOutput, '01_safe_rewrite.js')), false);
  assert.equal(fs.existsSync(path.join(reusedOutput, 'metrics.json')), false);
  assert.equal(fs.readFileSync(path.join(reusedOutput, 'final.js'), 'utf8'), fs.readFileSync(path.join(fixtures, 'parse-error.js'), 'utf8'));

  const invalidUtf8Input = path.join(tempDir, 'invalid-utf8.js');
  const invalidUtf8Bytes = Buffer.from([0x2f, 0x2f, 0x20, 0xff, 0x0a]);
  fs.writeFileSync(invalidUtf8Input, invalidUtf8Bytes);
  const invalidUtf8 = run(invalidUtf8Input, 'invalid-utf8');
  assert.equal(invalidUtf8.result.status, 2);
  assert.deepEqual(fs.readFileSync(path.join(invalidUtf8.output, '00_source.js')), invalidUtf8Bytes);
  assert.deepEqual(fs.readFileSync(path.join(invalidUtf8.output, 'final.js')), invalidUtf8Bytes);
  const invalidUtf8Report = JSON.parse(fs.readFileSync(path.join(invalidUtf8.output, 'pipeline-report.json'), 'utf8'));
  assert.equal(invalidUtf8Report.failedStep, 'input-encoding');

  const overlappingOutput = path.join(tempDir, 'overlapping-output');
  fs.mkdirSync(overlappingOutput);
  const overlappingInput = path.join(overlappingOutput, 'final.js');
  const overlappingBytes = Buffer.from('globalThis.__overlapMustSurvive = true;\n');
  fs.writeFileSync(overlappingInput, overlappingBytes);
  const overlapResult = spawnSync(process.execPath, [runner, overlappingInput, overlappingOutput], { encoding: 'utf8', windowsHide: true });
  assert.equal(overlapResult.status, 1);
  assert.deepEqual(fs.readFileSync(overlappingInput), overlappingBytes);
  assert.equal(fs.existsSync(path.join(overlappingOutput, '00_source.js')), false);

  const aliasDir = path.join(tempDir, 'overlap-alias');
  let aliasCreated = false;
  try {
    fs.symlinkSync(overlappingOutput, aliasDir, process.platform === 'win32' ? 'junction' : 'dir');
    aliasCreated = true;
  } catch (_) {}
  if (aliasCreated) {
    const aliasInput = path.join(aliasDir, 'final.js');
    const aliasResult = spawnSync(process.execPath, [runner, aliasInput, overlappingOutput], { encoding: 'utf8', windowsHide: true });
    assert.equal(aliasResult.status, 1);
    assert.deepEqual(fs.readFileSync(overlappingInput), overlappingBytes);
  }

  const hintOutput = path.join(tempDir, 'hint-redaction');
  const sensitiveHint = 'TOKEN_HINT_LEAK_PROBE';
  const hintResult = spawnSync(process.execPath, [runner, path.join(fixtures, 'safe-sample.js'), hintOutput, sensitiveHint], { encoding: 'utf8', windowsHide: true });
  assert.equal(hintResult.status, 0, hintResult.stderr || hintResult.stdout);
  const hintDetectionText = fs.readFileSync(path.join(hintOutput, 'detection.json'), 'utf8');
  assert.doesNotMatch(hintDetectionText, /TOKEN_HINT_LEAK_PROBE/);
  const hintDetection = JSON.parse(hintDetectionText);
  assert.equal(hintDetection.hintProvided, true);
  assert.equal(hintDetection.hintLength, sensitiveHint.length);

  console.log('Static AST profile tests: ok');
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
