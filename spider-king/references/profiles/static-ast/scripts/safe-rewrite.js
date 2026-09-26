const { generateSource, isIdentifierName, parseFile, parseSource, t, traverse, writeFileAtomic } = require('./ast-shared');

function containsHoistSensitiveDeclaration(branchPath) {
  if (!branchPath || !branchPath.node) return false;
  if (branchPath.isFunctionDeclaration() || (branchPath.isVariableDeclaration() && branchPath.node.kind === 'var')) {
    return true;
  }

  let found = false;
  branchPath.traverse({
    FunctionDeclaration(path) {
      found = true;
      path.stop();
    },
    VariableDeclaration(path) {
      if (path.node.kind !== 'var') return;
      found = true;
      path.stop();
    },
  });
  return found;
}

function rewrite(ast) {
  const changes = {
    computedMembers: 0,
    booleanBranches: 0,
  };

  traverse(ast, {
    MemberExpression(path) {
      const node = path.node;
      if (!node.computed || !t.isStringLiteral(node.property) || !isIdentifierName(node.property.value)) return;
      node.property = t.identifier(node.property.value);
      node.computed = false;
      changes.computedMembers += 1;
    },
    OptionalMemberExpression(path) {
      const node = path.node;
      if (!node.computed || !t.isStringLiteral(node.property) || !isIdentifierName(node.property.value)) return;
      node.property = t.identifier(node.property.value);
      node.computed = false;
      changes.computedMembers += 1;
    },
    IfStatement(path) {
      const test = path.node.test;
      if (!t.isBooleanLiteral(test)) return;
      if (
        containsHoistSensitiveDeclaration(path.get('consequent')) ||
        containsHoistSensitiveDeclaration(path.get('alternate'))
      ) return;
      const replacement = test.value ? path.node.consequent : path.node.alternate;
      if (replacement) path.replaceWith(replacement);
      else path.replaceWith(t.emptyStatement());
      changes.booleanBranches += 1;
    },
  });
  return changes;
}

function main() {
  const [, , inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    console.error('Usage: node safe-rewrite.js <input.js> <output.js>');
    process.exit(1);
  }
  const { ast } = parseFile(inputPath);
  const changes = rewrite(ast);
  const output = generateSource(ast);
  parseSource(output);
  writeFileAtomic(outputPath, output);
  process.stdout.write(JSON.stringify({ changes }) + '\n');
}

if (require.main === module) main();

module.exports = { containsHoistSensitiveDeclaration, rewrite };
