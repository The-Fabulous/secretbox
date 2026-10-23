export function menuToJson(items) {
  return JSON.stringify({
    currency: 'KZT',
    items: items.map(({ name, size_ml, price }) => ({ name, size_ml: size_ml ?? null, price })),
  }, null, 2);
}

export function compareItems(a, b, key) {
  if (key === 'name') return a.name.localeCompare(b.name);
  if (key === 'size') {
    // Напитки без указанного объёма всегда в конце списка.
    if (!a.size_ml && !b.size_ml) return 0;
    if (!a.size_ml) return 1;
    if (!b.size_ml) return -1;
    return a.size_ml - b.size_ml;
  }
  return Number(a.price) - Number(b.price);
}

