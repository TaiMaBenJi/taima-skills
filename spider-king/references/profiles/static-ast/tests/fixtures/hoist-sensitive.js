if (false) {
  var deadBranchBinding = 1;
}

if (false) {
  function deadBranchFunction() {
    return 1;
  }
}

globalThis.__staticAstHoistState = [
  typeof deadBranchBinding + ':' + String(deadBranchBinding),
  typeof deadBranchFunction + ':' + String(deadBranchFunction),
].join('|');
