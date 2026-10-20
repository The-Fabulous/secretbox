// Категории напитков для каталога.
//
// Как это работает: у напитка нет поля «категория», поэтому мы определяем её
// по словам в названии. Правила в RULES проверяются СВЕРХУ ВНИЗ, побеждает
// первое совпадение. Поэтому более конкретные правила (например, «айс ти»)
// стоят выше общих (например, «чай»).
//
// Слова в правилах пишутся в нижнем регистре и совпадают с НАЧАЛОМ слова:
// «матч» подойдёт к «матча», «матчу», а «raf» — к «Raf», но не к «Draft».
// Чтобы добавить новое слово — просто допишите его в нужный список.

export const CATEGORIES = [
  { id: 'coffee', label: 'Coffee', color: '#8a5a3c' },
  { id: 'iced-coffee', label: 'Iced coffee', color: '#5f8aa3' },
  { id: 'matcha', label: 'Matcha', color: '#7d9b6a' },
  { id: 'tea', label: 'Tea', color: '#b0823f' },
  { id: 'iced-tea', label: 'Iced tea', color: '#c46f5a' },
  { id: 'lemonade', label: 'Lemonade', color: '#c2a02a' },
  { id: 'shakes', label: 'Smoothies & shakes', color: '#a8658a' },
  { id: 'juice', label: 'Fresh juice', color: '#d0883a' },
  { id: 'cocoa', label: 'Cocoa & chocolate', color: '#6b4a3a' },
  { id: 'other', label: 'Other', color: '#9a9288' },
];

const RULES = [
  ['matcha', ['матч', 'matcha']],
  ['iced-tea', ['айс ти', 'айсти', 'ice tea', 'iced tea', 'ист ти', 'ice ti']],
  ['lemonade', ['лимонад', 'lemonade', 'мохито', 'mojito']],
  ['juice', ['фреш', 'свежевыжат', 'сок']],
  ['shakes', ['смузи', 'smoothie', 'коктейл', 'milkshake', 'милкшейк', 'шейк', 'shake']],
  // Фраппе делаем холодным кофе раньше какао, чтобы «Frappe Шоколад» не попал в какао.
  ['iced-coffee', ['frapp', 'фрап']],
  ['cocoa', ['какао', 'шоколад', 'chocolate', 'șokolad', 'şokolad', 'бэйби', 'бейби']],
  ['iced-coffee', ['айс', 'ice', 'cold brew', 'нитро', 'nitro', 'тоник', 'tonic', 'бамбл', 'bumble', 'гляссе', 'glasse']],
  ['tea', ['чай', 'tea', 'шай', 'сенча', 'карак', 'karkade']],
  ['coffee', [
    'эспрессо', 'espresso', 'американо', 'americano', 'латте', 'latte',
    'капучино', 'cappuccino', 'capuccino', 'флэт', 'флат', 'flat white',
    'раф', 'raf', 'моккачино', 'mocaccino', 'mocha', 'мокко',
    'пуровер', 'pour', 'батч', 'batch', 'брю', 'brew',
    'кофе', 'coffee', 'доп шот', 'туран', 'спэниш', 'spanish',
  ]],
];

const CATEGORY_BY_ID = Object.fromEntries(CATEGORIES.map((category) => [category.id, category]));

export function getCategory(id) {
  return CATEGORY_BY_ID[id] || CATEGORY_BY_ID.other;
}

// Приводит название к виду " айс ти манго имбирь": нижний регистр, дефисы и
// знаки препинания заменены пробелами. Пробел в начале нужен, чтобы искать
// слова по началу (' раф' найдёт «Раф», но не «Графин»).
function normalize(name) {
  return ` ${String(name).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()}`;
}

export function categorize(name) {
  const text = normalize(name);
  for (const [categoryId, words] of RULES) {
    if (words.some((word) => text.includes(` ${word}`))) return categoryId;
  }
  return 'other';
}
