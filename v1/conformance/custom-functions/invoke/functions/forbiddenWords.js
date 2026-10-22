module.exports = (targetVal, options) => {
  const problems = [];
  for (const word of options.forbidden) {
    if (String(targetVal).includes(word)) {
      problems.push({ message: `Contains "${word}".` });
    }
  }
  return problems;
};
