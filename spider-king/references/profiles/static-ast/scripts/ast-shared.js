const fs = require('fs');
const crypto = require('crypto');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const generator = require('@babel/generator').default;
const t = require('@babel/types');

const PARSER_PLUGINS = [
  'jsx',
  'classProperties',
  'classPrivateProperties',
  'classPrivateMethods',
  'optionalChaining',
  'nullishCoalescingOperator',
  'dynamicImport',
  'topLevelAwait',
];

function parseSource(source) {
  return parser.parse(source, {
    sourceType: 'unambiguous',
    allowReturnOutsideFunction: true,
    errorRecovery: false,
    plugins: PARSER_PLUGINS,
  });
}

function generateSource(ast) {
  return generator(ast, {
    comments: true,
    compact: false,
    jsescOption: { minimal: true },
  }).code + '\n';
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function writeFileAtomic(filePath, value) {
  const temporaryPath = `${filePath}.tmp-${process.pid}`;
  try {
    fs.writeFileSync(temporaryPath, value, typeof value === 'string' ? 'utf8' : undefined);
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    fs.renameSync(temporaryPath, filePath);
  } finally {
    if (fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath);
  }
}

function isLiteralLike(node) {
  return Boolean(node) && (
    t.isStringLiteral(node) ||
    t.isNumericLiteral(node) ||
    t.isBooleanLiteral(node) ||
    t.isNullLiteral(node) ||
    t.isBigIntLiteral(node) ||
    t.isRegExpLiteral(node) ||
    t.isIdentifier(node, { name: 'undefined' })
  );
}

function isIdentifierName(value) {
  return /^[A-Za-z_$][\w$]*$/.test(value);
}

function countOpcodeIfChains(ast) {
  const statementLists = [];
  traverse(ast, {
    Program(path) { statementLists.push(path.node.body); },
    BlockStatement(path) { statementLists.push(path.node.body); },
    SwitchCase(path) { statementLists.push(path.node.consequent); },
  });
  let count = 0;
  for (const statements of statementLists) {
    for (let index = 0; index < statements.length; index += 1) {
      const first = statements[index];
      if (!t.isIfStatement(first) || first.alternate) continue;
      const descriptor = opcodeIfDescriptor(first);
      if (!descriptor) continue;
      let length = 1;
      let cursor = index + 1;
      while (cursor < statements.length) {
        const next = statements[cursor];
        const nextDescriptor = opcodeIfDescriptor(next);
        if (!nextDescriptor || nextDescriptor.discriminant !== descriptor.discriminant) break;
        length += 1;
        cursor += 1;
      }
      if (length >= 2) {
        count += length;
        index = cursor - 1;
      }
    }
  }
  return count;
}

function opcodeIfDescriptor(node) {
  if (!t.isIfStatement(node) || node.alternate || !t.isBinaryExpression(node.test)) return null;
  if (!['==', '===', '!=', '!=='].includes(node.test.operator)) return null;
  const leftLiteral = isLiteralLike(node.test.left);
  const rightLiteral = isLiteralLike(node.test.right);
  if (leftLiteral === rightLiteral) return null;
  const discriminant = leftLiteral ? node.test.right : node.test.left;
  const literal = leftLiteral ? node.test.left : node.test.right;
  if (!t.isIdentifier(discriminant) && !t.isMemberExpression(discriminant)) return null;
  return { discriminant: generateSource(t.file(t.program([t.expressionStatement(discriminant)]))).trim(), literal };
}

function collectMetrics(source, ast = null) {
  const parsed = ast || parseSource(source);
  const metrics = {
    lineCount: source.split(/\r?\n/).length,
    stringArrayCount: 0,
    dispatcherObjectCount: 0,
    loopSwitchCount: 0,
    opcodeIfChainCount: countOpcodeIfChains(parsed),
    hexIdentifierCount: (source.match(/\b_0x[a-f0-9]+\b/gi) || []).length,
    dynamicExecutionCount: 0,
    wasmUseCount: 0,
    computedMemberCount: 0,
  };

  traverse(parsed, {
    ArrayExpression(path) {
      const elements = path.node.elements.filter(Boolean);
      if (elements.length >= 4 && elements.every((node) => t.isStringLiteral(node))) metrics.stringArrayCount += 1;
    },
    ObjectExpression(path) {
      const functions = path.node.properties.filter((property) => (
        t.isObjectProperty(property) && (t.isFunctionExpression(property.value) || t.isArrowFunctionExpression(property.value))
      ));
      if (functions.length >= 2) metrics.dispatcherObjectCount += 1;
    },
    WhileStatement(path) {
      if (path.node.body && t.isBlockStatement(path.node.body) && path.node.body.body.some((node) => t.isSwitchStatement(node))) metrics.loopSwitchCount += 1;
    },
    ForStatement(path) {
      if (path.node.body && t.isBlockStatement(path.node.body) && path.node.body.body.some((node) => t.isSwitchStatement(node))) metrics.loopSwitchCount += 1;
    },
    CallExpression(path) {
      if (t.isIdentifier(path.node.callee, { name: 'eval' }) || t.isIdentifier(path.node.callee, { name: 'Function' })) metrics.dynamicExecutionCount += 1;
    },
    NewExpression(path) {
      if (t.isIdentifier(path.node.callee, { name: 'Function' })) metrics.dynamicExecutionCount += 1;
    },
    Identifier(path) {
      if (path.node.name === 'WebAssembly') metrics.wasmUseCount += 1;
    },
    MemberExpression(path) {
      if (path.node.computed) metrics.computedMemberCount += 1;
    },
    OptionalMemberExpression(path) {
      if (path.node.computed) metrics.computedMemberCount += 1;
    },
  });
  return metrics;
}

function detectFamilies(metrics) {
  const families = [];
  if (metrics.stringArrayCount > 0) families.push('string-table');
  if (metrics.dispatcherObjectCount > 0) families.push('dispatcher');
  if (metrics.loopSwitchCount > 0) families.push('loop-switch');
  if (metrics.opcodeIfChainCount > 0) families.push('opcode-if-chain');
  if (metrics.hexIdentifierCount > 0) families.push('hex-identifiers');
  if (metrics.dynamicExecutionCount > 0) families.push('dynamic-execution');
  if (metrics.wasmUseCount > 0) families.push('wasm');
  return families;
}

function parseFile(filePath) {
  const source = fs.readFileSync(filePath, 'utf8');
  return { source, ast: parseSource(source) };
}

module.exports = {
  PARSER_PLUGINS,
  collectMetrics,
  detectFamilies,
  generateSource,
  isIdentifierName,
  parseFile,
  parseSource,
  sha256,
  t,
  traverse,
  writeFileAtomic,
};
