module.exports = (v) => (typeof v === 'string' && v.trim() !== '' ? [] : [{ message: 'Title is empty.' }]);
