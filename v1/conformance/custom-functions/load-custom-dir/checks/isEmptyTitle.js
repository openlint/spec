module.exports = (targetVal) => {
  if (typeof targetVal !== 'string' || targetVal.trim() === '') {
    return [{ message: 'Title is empty.' }];
  }
  return [];
};
