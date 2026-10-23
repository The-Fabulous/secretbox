import { useEffect, useMemo, useState } from 'react';
import { api, authConfig } from '../api';
import { CATEGORIES, categorize } from '../categories';
import { usernameFromToken } from '../utils/session';
import { compareItems, menuToJson } from '../utils/menu';

export default function useWorkspace() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [authMode, setAuthMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [shops, setShops] = useState([]);
  const [selectedShop, setSelectedShop] = useState('');
  const [menu, setMenu] = useState({ items: [], updated_at: '' });
  const [menuLoading, setMenuLoading] = useState(false);
  const [menuError, setMenuError] = useState('');
  const [activeView, setActiveView] = useState('catalog');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState({ key: '', dir: 'asc' });
  const [manualText, setManualText] = useState('');
  const [savingMenu, setSavingMenu] = useState(false);
  const [updateMessage, setUpdateMessage] = useState('');
  const [analytics, setAnalytics] = useState([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatError, setChatError] = useState('');

  function logout() {
    localStorage.removeItem('token');
    setToken('');
    setShops([]);
    setSelectedShop('');
    setMenu({ items: [], updated_at: '' });
    setMenuLoading(false);
    setAnalytics([]);
    setAnalyticsLoading(false);
    setChatMessages([]);
    setCategory('all');
    setSort({ key: '', dir: 'asc' });
    setActiveView('catalog');
  }

  useEffect(() => {
    if (!token) return undefined;
    let current = true;
    api.get('/coffee-shops', authConfig(token))
      .then(({ data }) => {
        if (!current) return;
        const availableShops = data.shops || [];
        setShops(availableShops);
        setSelectedShop((selected) => (
          availableShops.includes(selected) ? selected : (availableShops[0] || '')
        ));
      })
      .catch((error) => {
        if (error.response?.status === 401) logout();
        else if (current) setMenuError('Could not load cafes. Check that the Python API is running.');
      });
    return () => { current = false; };
  }, [token]);

  useEffect(() => {
    if (!token || !selectedShop) return undefined;
    let current = true;
    api.get(`/menu/${encodeURIComponent(selectedShop)}`, authConfig(token))
      .then(({ data }) => {
        if (!current) return;
        const nextMenu = { items: data.items || [], updated_at: data.updated_at || '' };
        setMenu(nextMenu);
        setManualText(menuToJson(nextMenu.items));
      })
      .catch((error) => {
        if (!current) return;
        if (error.response?.status === 401) logout();
        else setMenuError('This cafe menu could not be loaded. Please try again.');
      })
      .finally(() => {
        if (current) setMenuLoading(false);
      });
    return () => { current = false; };
  }, [token, selectedShop]);

  useEffect(() => {
    if (!token || activeView !== 'analytics') return undefined;
    let current = true;
    api.get('/analytics/compare', authConfig(token))
      .then(({ data }) => {
        if (current) setAnalytics(Array.isArray(data) ? data : []);
      })
      .catch((error) => {
        if (!current) return;
        if (error.response?.status === 401) logout();
        else setAnalyticsError('Price comparison is unavailable right now.');
      })
      .finally(() => {
        if (current) setAnalyticsLoading(false);
      });
    return () => { current = false; };
  }, [token, activeView]);

  useEffect(() => {
    if (!token || activeView !== 'chat') return undefined;
    let current = true;
    const fetchMessages = () => {
      api.get('/chat', authConfig(token))
        .then(({ data }) => {
          if (current) setChatMessages(data.messages || []);
        })
        .catch((error) => {
          if (!current) return;
          if (error.response?.status === 401) logout();
          else setChatError('The team chat could not be reached.');
        });
    };
    fetchMessages();
    const timer = window.setInterval(fetchMessages, 5000);
    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [token, activeView]);

  // Каждому напитку добавляем категорию, определённую по названию (см. categories.js).
  const categorizedItems = useMemo(
    () => (menu.items || []).map((item) => ({ ...item, category: categorize(item.name) })),
    [menu.items],
  );

  // Сколько напитков в каждой категории — показываем только те, что есть в меню этой кофейни.
  const categoryCounts = useMemo(() => {
    const counts = {};
    categorizedItems.forEach((item) => { counts[item.category] = (counts[item.category] || 0) + 1; });
    return counts;
  }, [categorizedItems]);

  const availableCategories = CATEGORIES.filter((entry) => categoryCounts[entry.id]);
  // Если выбранной категории нет в меню новой кофейни, показываем «All».
  const activeCategory = category === 'all' || categoryCounts[category] ? category : 'all';

  const visibleItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    const filtered = categorizedItems.filter((item) => (
      (activeCategory === 'all' || item.category === activeCategory)
      && item.name.toLocaleLowerCase().includes(query)
    ));
    if (!sort.key) return filtered;
    const factor = sort.dir === 'desc' ? -1 : 1;
    return [...filtered].sort((a, b) => {
      const result = compareItems(a, b, sort.key);
      const sizeMissing = sort.key === 'size' && (!a.size_ml || !b.size_ml);
      return sizeMissing ? result : result * factor;
    });
  }, [categorizedItems, activeCategory, search, sort]);

  function toggleSort(key) {
    // Клик по заголовку: по возрастанию → по убыванию → исходный порядок меню.
    setSort((current) => {
      if (current.key !== key) return { key, dir: 'asc' };
      if (current.dir === 'asc') return { key, dir: 'desc' };
      return { key: '', dir: 'asc' };
    });
  }

  function sortState(key) {
    if (sort.key !== key) return 'none';
    return sort.dir === 'asc' ? 'ascending' : 'descending';
  }

  const displayName = username || usernameFromToken(token);

  async function submitAuth(event) {
    event.preventDefault();
    setAuthMessage('');
    const endpoint = authMode === 'login' ? '/login' : '/register';
    try {
      const { data } = await api.post(endpoint, { username, password });
      if (authMode === 'register') {
        setAuthMode('login');
        setPassword('');
        setAuthMessage(data.detail || 'Account created. Please sign in.');
        return;
      }
      localStorage.setItem('token', data.token);
      setMenuLoading(true);
      setMenuError('');
      setToken(data.token);
      setPassword('');
    } catch (error) {
      setAuthMessage(error.response?.data?.detail || 'Could not connect to the Python API.');
    }
  }

  async function refreshMenu() {
    const { data } = await api.get(`/menu/${encodeURIComponent(selectedShop)}`, authConfig(token));
    const nextMenu = { items: data.items || [], updated_at: data.updated_at || '' };
    setMenu(nextMenu);
    setManualText(menuToJson(nextMenu.items));
  }

  async function saveMenu(contents) {
    if (!selectedShop) return;
    setSavingMenu(true);
    setUpdateMessage('');
    setMenuError('');
    try {
      await api.put(
        `/api/menus/${encodeURIComponent(selectedShop)}`,
        contents,
        { headers: { ...authConfig(token).headers, 'Content-Type': 'text/plain; charset=utf-8' } },
      );
      await refreshMenu();
      setUpdateMessage('Menu updated successfully.');
    } catch (error) {
      const detail = error.response?.data?.detail;
      setMenuError(typeof detail === 'string' ? detail : 'Update failed. Please try again.');
    } finally {
      setSavingMenu(false);
    }
  }

  async function importFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const contents = await file.text();
    setManualText(contents);
    await saveMenu(contents);
    event.target.value = '';
  }

  async function sendChat(event) {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setChatError('');
    try {
      await api.post('/chat', { text }, authConfig(token));
      setChatInput('');
      const { data } = await api.get('/chat', authConfig(token));
      setChatMessages(data.messages || []);
    } catch (error) {
      if (error.response?.status === 401) logout();
      else setChatError('Message could not be sent. Please try again.');
    }
  }

  const analyticsColumns = analytics.length
    ? [...new Set(analytics.flatMap((row) => Object.keys(row)))]
    : [];

  return {
    token, displayName, logout, authMode, username,
    password, authMessage, setUsername, setPassword, setAuthMode,
    setAuthMessage, submitAuth, shops, selectedShop, setMenuLoading,
    setMenuError, setSelectedShop, setSearch, setCategory, setUpdateMessage,
    visibleItems, menu, search, menuError, updateMessage,
    menuLoading, availableCategories, activeCategory, categoryCounts, sortState,
    toggleSort, sort, manualText, setManualText, savingMenu,
    importFile, saveMenu, analytics, analyticsError, analyticsLoading,
    analyticsColumns, chatError, chatMessages, sendChat, chatInput,
    setChatInput, activeView, setActiveView, setAnalyticsLoading, setAnalyticsError,
  };
}
