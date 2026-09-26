const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { TextDecoder } = require('util');
const { sha256, writeFileAtomic } = require('./ast-shared');

const STEP_TIMEOUT_MS = 120000;

function safeError(result) {
  const stderr = result && result.stderr ? String(result.stderr) : '';
  return {
    stderrSha256: sha256(stderr),
    stderrLength: stderr.length,
    message: stderr.split(/\r?\n/)[0].slice(0, 240),
  };
}

function runStep(scriptPath, args) {
  const started = Date.now();
  const result = spawnSync(process.execPath, [scriptPath, ...args], {
    cwd: path.resolve(__dirname, '..'),
    encoding: 'utf8',
    timeout: STEP_TIMEOUT_MS,
    windowsHide: true,
  });
  const timedOut = Boolean(result.error && result.error.code === 'ETIMEDOUT');
  return {
    status: timedOut ? 'timed_out' : result.status === 0 ? 'ok' : 'failed',
    exitCode: typeof result.status === 'number' ? result.status : null,
    durationMs: Date.now() - started,
    stdout: result && result.stdout ? String(result.stdout) : '',
    error: result.status === 0 ? null : safeError(result),
  };
}

function stepSummary(step) {
  const { stdout, ...summary } = step;
  return summary;
}

function removeGeneratedArtifacts(paths) {
  for (const filePath of paths) {
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  }
}

function pathKey(filePath) {
  const resolved = path.resolve(filePath);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function canonicalPathKey(filePath) {
  const absolute = path.resolve(filePath);
  try {
    return pathKey(fs.realpathSync.native(absolute));
  } catch (_) {
    try {
      const canonicalParent = fs.realpathSync.native(path.dirname(absolute));
      return pathKey(path.join(canonicalParent, path.basename(absolute)));
    } catch (_) {
      return pathKey(absolute);
    }
  }
}

function assertInputPathDisjoint(inputPath, generatedPaths) {
  const inputKeys = new Set([pathKey(inputPath), canonicalPathKey(inputPath)]);
  if (generatedPaths.some((filePath) => inputKeys.has(pathKey(filePath)) || inputKeys.has(canonicalPathKey(filePath)))) {
    throw new Error('input path overlaps a generated artifact');
  }
}

function isValidUtf8(value) {
  try {
    new TextDecoder('utf-8', { fatal: true }).decode(value);
    return true;
  } catch (_) {
    return false;
  }
}

function main() {
  const [, , inputPath, outputDir, hint = ''] = process.argv;
  if (!inputPath || !outputDir) {
    console.error('Usage: node run-pipeline.js <input.js> <output-dir> [hint]');
    process.exit(1);
  }
  const sourcePath = path.join(outputDir, '00_source.js');
  const rewritePath = path.join(outputDir, '01_safe_rewrite.js');
  const detectionPath = path.join(outputDir, 'detection.json');
  const metricsPath = path.join(outputDir, 'metrics.json');
  const reportPath = path.join(outputDir, 'pipeline-report.json');
  const finalPath = path.join(outputDir, 'final.js');
  const generatedPaths = [
    sourcePath,
    rewritePath,
    detectionPath,
    metricsPath,
    reportPath,
    finalPath,
  ];
  try {
    assertInputPathDisjoint(inputPath, generatedPaths);
  } catch (_) {
    console.error('Refusing to overwrite an input path reserved for generated artifacts');
    process.exit(1);
  }
  const sourceBytes = fs.readFileSync(inputPath);
  fs.mkdirSync(outputDir, { recursive: true });
  removeGeneratedArtifacts(generatedPaths);
  writeFileAtomic(sourcePath, sourceBytes);

  const report = {
    inputFile: path.basename(inputPath),
    inputSha256: sha256(sourceBytes),
    selectedPipeline: 'generic-static-safe',
    targetCodeExecuted: false,
    status: 'ok',
    lastGoodFile: '00_source.js',
    steps: [],
  };

  if (!isValidUtf8(sourceBytes)) {
    report.status = 'failed';
    report.failedStep = 'input-encoding';
    report.steps.push({
      id: 'input-encoding',
      status: 'failed',
      exitCode: null,
      durationMs: 0,
      error: {
        stderrSha256: null,
        stderrLength: 0,
        message: 'input is not valid UTF-8',
      },
    });
    writeFileAtomic(finalPath, sourceBytes);
    report.finalFile = 'final.js';
    report.finalSha256 = sha256(sourceBytes);
    writeFileAtomic(reportPath, JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ status: report.status, lastGoodFile: report.lastGoodFile }) + '\n');
    process.exit(2);
  }

  const detect = runStep(path.join(__dirname, 'detect-structure.js'), [sourcePath, hint]);
  report.steps.push({ id: 'detect', ...stepSummary(detect) });
  if (detect.status === 'ok') {
    try {
      const detection = JSON.parse(detect.stdout);
      writeFileAtomic(detectionPath, JSON.stringify(detection, null, 2) + '\n');
      report.families = detection.families;
    } catch (error) {
      report.status = 'failed';
      report.failedStep = 'detect-output';
      report.steps[report.steps.length - 1].error = {
        stderrSha256: null,
        stderrLength: 0,
        message: 'invalid detector JSON output',
      };
    }
  } else {
    report.status = detect.status;
    report.failedStep = 'detect';
  }

  if (report.status === 'ok') {
    const rewrite = runStep(path.join(__dirname, 'safe-rewrite.js'), [sourcePath, rewritePath]);
    report.steps.push({ id: 'safe-rewrite', ...stepSummary(rewrite) });
    if (rewrite.status === 'ok') report.lastGoodFile = '01_safe_rewrite.js';
    else {
      report.status = rewrite.status;
      report.failedStep = 'safe-rewrite';
    }
  }

  const currentPath = path.join(outputDir, report.lastGoodFile);
  const metrics = runStep(path.join(__dirname, 'collect-metrics.js'), [currentPath, metricsPath]);
  report.steps.push({ id: 'metrics', ...stepSummary(metrics) });
  if (metrics.status !== 'ok' && report.status === 'ok') {
    report.status = metrics.status;
    report.failedStep = 'metrics';
  }
  writeFileAtomic(finalPath, fs.readFileSync(currentPath));
  report.finalFile = 'final.js';
  report.finalSha256 = sha256(fs.readFileSync(finalPath));
  writeFileAtomic(reportPath, JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ status: report.status, lastGoodFile: report.lastGoodFile }) + '\n');
  if (report.status !== 'ok') process.exit(2);
}

if (require.main === module) main();

module.exports = { assertInputPathDisjoint, canonicalPathKey, isValidUtf8, removeGeneratedArtifacts, runStep, safeError, stepSummary };
