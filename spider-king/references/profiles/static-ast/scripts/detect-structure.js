const fs = require('fs');
const path = require('path');
const { collectMetrics, detectFamilies, parseSource, sha256 } = require('./ast-shared');

function main() {
  const [, , inputPath, hint = ''] = process.argv;
  if (!inputPath) {
    console.error('Usage: node detect-structure.js <input.js> [hint]');
    process.exit(1);
  }

  const source = fs.readFileSync(inputPath, 'utf8');
  let ast;
  try {
    ast = parseSource(source);
  } catch (error) {
    process.stderr.write('parse failed: ' + String(error.message || error).split(/\r?\n/)[0] + '\n');
    process.exit(2);
  }

  const metrics = collectMetrics(source, ast);
  const families = detectFamilies(metrics);
  const report = {
    inputFile: path.basename(inputPath),
    inputSha256: sha256(source),
    hintProvided: String(hint).length > 0,
    hintLength: String(hint).length,
    selectedPipeline: 'generic-static-safe',
    ambiguous: families.length > 1 || families.length === 0,
    targetCodeExecuted: false,
    families,
    metrics,
  };
  process.stdout.write(JSON.stringify(report) + '\n');
}

if (require.main === module) main();
