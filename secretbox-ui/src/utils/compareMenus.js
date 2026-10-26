export function compareMenus(menus) {
  const groups = new Map();
  for (const [shop, menu] of Object.entries(menus)) {
    for (const item of menu.items) {
      const name = item.name.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
      const key = JSON.stringify([name, item.size_ml ?? null]);
      if (!groups.has(key)) groups.set(key, { item, prices: new Map() });
      groups.get(key).prices.set(shop, item.price);
    }
  }
  return [...groups.values()].filter(({ prices }) => prices.size >= 2).map(({ item, prices }) => ({
    'Напиток': item.name,
    'Объём': item.size_ml ? `${item.size_ml} мл` : 'Не указан',
    ...Object.fromEntries([...prices].map(([shop, price]) => [shop, `${price} ₸`])),
    'Разброс': Math.max(...prices.values()) - Math.min(...prices.values()),
  }));
}
