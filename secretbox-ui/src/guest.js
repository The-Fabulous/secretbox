import { compareMenus } from './utils/compareMenus';

// Bundle the repository's real menus so browsing works on static hosting too.
const documents = import.meta.glob('../../objects/*_menu.json', { eager: true, import: 'default' });
export const guestMenus = Object.fromEntries(Object.entries(documents).map(([path, document]) => [
  path.split('/').at(-1).replace(/_menu\.json$/, ''),
  { items: document.items, updated_at: '' },
]));
export const guestShops = Object.keys(guestMenus).sort();
export const guestAnalytics = compareMenus(guestMenus);
