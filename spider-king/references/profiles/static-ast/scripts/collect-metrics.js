const fs = require('fs');
const { collectMetrics, detectFamilies, parseSource, sha256, writeFileAtomic } = require('./ast-shared');

function main() {
  const [, , inputPath, outputPath = ''] = process.argv;
  if (!inputPath) {
    console.error('Usage: node collect-metrics.js <input.js> [output.json]');
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
  const result = {
    file: require('path').basename(inputPath),
    sha256: sha256(source),
    metrics: collectMetrics(source, ast),
    families: detectFamilies(collectMetrics(source, ast)),
  };
  const json = JSON.stringify(result, null, 2) + '\n';
  if (outputPath) writeFileAtomic(outputPath, json);
  else process.stdout.write(json);
}

if (require.main === module) main();

module.exports = { collectMetrics, detectFamilies };
