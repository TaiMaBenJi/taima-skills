const table = ['alpha', 'beta', 'gamma', 'delta'];
const worker = { run(value) { return value + 1; } };
const result = worker['run'](1);
if (true) {
  globalThis.__staticAstResult = table[1] + ':' + result;
}
if (false) {
  throw new Error('dead branch must remain unexecuted');
}
