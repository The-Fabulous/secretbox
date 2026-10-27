import ayuMenu from '../../objects/Ayu_menu.txt?raw';
import espressodayMenu from '../../objects/Espressoday_menu.txt?raw';
import masterMenu from '../../objects/Master_menu.txt?raw';
import slonMenu from '../../objects/Slon_menu.txt?raw';
import zebraMenu from '../../objects/Zebra_menu.txt?raw';

const MENU_TEXTS = {
  Ayu: ayuMenu,
  Espressoday: espressodayMenu,
  Master: masterMenu,
  Slon: slonMenu,
  Zebra: zebraMenu,
};

function parseMenu(text) {
  return text.split(/\r?\n/).flatMap((line) => {
    const match = line.trim().match(/^(.+?)\s*[-—–]\s*([\d][\d\s.,]*)\s*(?:₸|KZT)?\s*$/i);
    if (!match) return [];

    const sizeMatch = match[1].match(/(?<!\d)(\d+(?:[.,]\d+)?)\s*(ml|мл|l|л)(?=$|[^\p{L}\p{N}])/iu);
    const size = sizeMatch
      ? Math.round(Number(sizeMatch[1].replace(',', '.')) * (/^(l|л)$/i.test(sizeMatch[2]) ? 1000 : 1))
      : null;
    const name = sizeMatch ? match[1].replace(sizeMatch[0], '').trim().replace(/[\s\-—–,()]+$/, '') : match[1].trim();
    const price = Number(match[2].replace(/\D/g, ''));

    if (!name || !price || (sizeMatch && (size <= 0 || size > 5000))) return [];
    return [{ name, size_ml: size, price, currency: '₸' }];
  });
}

export const GUEST_SHOPS = Object.keys(MENU_TEXTS).sort();

export const GUEST_MENUS = Object.fromEntries(
  Object.entries(MENU_TEXTS).map(([shop, text]) => [
    shop,
    { items: parseMenu(text), updated_at: '' },
  ]),
);

function normalizeName(name) {
  return [...name.toLocaleLowerCase()].filter((character) => /[\p{L}\p{N}]/u.test(character)).join('');
}

function compareMenus() {
  const grouped = new Map();
  GUEST_SHOPS.forEach((shop) => {
    GUEST_MENUS[shop].items.forEach((item) => {
      const key = `${normalizeName(item.name)}:${item.size_ml ?? ''}`;
      const row = grouped.get(key) || {
        Напиток: item.name,
        Объём: item.size_ml ? `${item.size_ml} мл` : 'Не указан',
        prices: {},
        numericPrices: [],
      };
      row.prices[shop] = `${item.price} ₸`;
      row.numericPrices.push(item.price);
      grouped.set(key, row);
    });
  });

  return [...grouped.values()]
    .filter((row) => Object.keys(row.prices).length >= 2)
    .map((row) => ({
      Напиток: row.Напиток,
      Объём: row.Объём,
      ...Object.fromEntries(GUEST_SHOPS.map((shop) => [shop, row.prices[shop] ?? null])),
      Разброс: Math.max(...row.numericPrices) - Math.min(...row.numericPrices),
    }));
}

export const GUEST_ANALYTICS = compareMenus();
