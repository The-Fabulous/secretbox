import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CATEGORIES, categorize, getCategory } from './categories';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const UPDATER_URL = import.meta.env.VITE_UPDATER_URL || 'http://127.0.0.1:8081';
const api = axios.create({ baseURL: API_URL });
const authConfig = (token) => ({ headers: { Authorization: `Bearer ${token}` } });

function formatDate(value) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Not recorded'
    : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function getGreeting(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 18) return 'Good afternoon';
  return 'Good evening';
}

// Имя пользователя лежит внутри токена (JWT), поэтому оно не пропадает после обновления страницы.
function usernameFromToken(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)).sub || '';
  } catch {
    return '';
  }
}

function compareItems(a, b, key) {
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

function App() {
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
        setManualText(nextMenu.items
          .map((item) => `${item.name}|${item.size_ml ? `${item.size_ml} ml` : ''}|${item.price}`)
          .join('\n'));
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
    setManualText(nextMenu.items
      .map((item) => `${item.name}|${item.size_ml ? `${item.size_ml} ml` : ''}|${item.price}`)
      .join('\n'));
  }

  async function saveMenu(contents) {
    if (!selectedShop) return;
    setSavingMenu(true);
    setUpdateMessage('');
    setMenuError('');
    try {
      await axios.put(
        `${UPDATER_URL}/api/menus/${encodeURIComponent(selectedShop)}`,
        contents,
        { headers: { ...authConfig(token).headers, 'Content-Type': 'text/plain; charset=utf-8' } },
      );
      await refreshMenu();
      setUpdateMessage('Menu updated successfully.');
    } catch (error) {
      const detail = error.response?.data?.detail;
      setMenuError(detail || 'Update failed. Make sure both the Java updater and Python API are running.');
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

  if (!token) {
    return (
      <main className="auth-page">
        <section className="auth-story">
          <a className="brand" href="/" aria-label="SecretBox home">
            <span className="brand-mark">S</span>
            <span>secretbox<span className="brand-period">.</span></span>
          </a>
          <div className="auth-copy">
            <p className="eyebrow">THE CAFE PRICE DESK</p>
            <h1>Good coffee.<br />Clear numbers.</h1>
            <p>Keep every cafe menu, cup size and price in one calm place.</p>
          </div>
          <div className="auth-cup" aria-hidden="true"><span /></div>
          <p className="auth-footnote">A better view of the coffee around you.</p>
        </section>
        <section className="auth-side">
          <div className="auth-card">
            <p className="eyebrow">{authMode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</p>
            <h2>{authMode === 'login' ? 'Sign in to SecretBox' : 'Create your account'}</h2>
            <p className="auth-subtitle">Your cafe menu workspace is waiting.</p>
            <form onSubmit={submitAuth} className="auth-form">
              <label>
                Username
                <input
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Your username"
                  required
                />
              </label>
              <label>
                Password
                <input
                  autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </label>
              {authMessage && <p className="form-message">{authMessage}</p>}
              <button className="button button-primary auth-submit" type="submit">
                {authMode === 'login' ? 'Sign in' : 'Create account'} <span aria-hidden="true">↗</span>
              </button>
            </form>
            <p className="auth-switch">
              {authMode === 'login' ? 'New to SecretBox?' : 'Already have an account?'}
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                  setAuthMessage('');
                }}
              >
                {authMode === 'login' ? 'Create an account' : 'Sign in'}
              </button>
            </p>
          </div>
          <span className="secure-note"><span aria-hidden="true">◈</span> Private menu workspace</span>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="SecretBox home">
          <span className="brand-mark">S</span>
          <span>secretbox<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-right">
          <span className="user-chip"><span className="user-dot" />{displayName || 'Cafe team'}</span>
          <button className="button button-quiet sign-out" onClick={logout}>Sign out <span aria-hidden="true">↗</span></button>
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome-row">
          <div>
            <p className="eyebrow">CAFE MENU INTELLIGENCE</p>
            <h1>{getGreeting()}{displayName ? `, ${displayName}` : ''}<span className="heading-period">.</span></h1>
            <p className="welcome-subtitle">A clear look at the drinks, sizes and prices on your watch.</p>
          </div>
          <div className="coffee-stamp" aria-hidden="true">
            <span className="stamp-steam">〰</span><span className="stamp-cup">▱</span>
            <span className="stamp-caption">BREW<br />BETTER</span>
          </div>
        </section>

        <section className="stat-grid" aria-label="Cafe menu overview">
          <article className="stat-card">
            <span className="stat-icon icon-peach">⌂</span>
            <span className="stat-label">CAFES TRACKED</span>
            <strong>{shops.length.toString().padStart(2, '0')}</strong>
            <span className="stat-note">In your price list</span>
          </article>
          <article className="stat-card">
            <span className="stat-icon icon-green">☕</span>
            <span className="stat-label">DRINKS IN VIEW</span>
            <strong>{(menu.items || []).length.toString().padStart(2, '0')}</strong>
            <span className="stat-note">{selectedShop || 'Choose a cafe'}</span>
          </article>
          <article className="stat-card stat-card-update">
            <span className="stat-icon icon-gold">↻</span>
            <span className="stat-label">MENU LAST UPDATED</span>
            <strong className="stat-date">{formatDate(menu.updated_at)}</strong>
            <span className="stat-note">From the latest cafe list</span>
          </article>
        </section>

        <nav className="view-tabs" aria-label="Main navigation">
          <button className={activeView === 'catalog' ? 'view-tab active' : 'view-tab'} onClick={() => setActiveView('catalog')}>
            <span aria-hidden="true">▤</span> Cafe menus
          </button>
          <button className={activeView === 'analytics' ? 'view-tab active' : 'view-tab'} onClick={() => {
            if (activeView !== 'analytics') setAnalyticsLoading(true);
            setAnalyticsError('');
            setActiveView('analytics');
          }}>
            <span aria-hidden="true">↗</span> Price comparison
          </button>
          <button className={activeView === 'chat' ? 'view-tab active' : 'view-tab'} onClick={() => setActiveView('chat')}>
            <span aria-hidden="true">◌</span> Team chat
          </button>
        </nav>

        {activeView === 'catalog' && (
          <section className="content-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">YOUR NEIGHBOURHOOD</p>
                <h2>Cafe menus</h2>
                <p className="panel-description">Browse current drinks, cup sizes and listed prices.</p>
              </div>
              <span className="live-badge"><span /> MENU DESK</span>
            </div>
            <div className="catalog-layout">
              <aside className="cafe-list">
                <p className="section-label">YOUR CAFES <span>{shops.length}</span></p>
                {shops.length ? shops.map((shop, index) => (
                  <button
                    className={selectedShop === shop ? 'cafe-option selected' : 'cafe-option'}
                    key={shop}
                    onClick={() => {
                      if (selectedShop !== shop) setMenuLoading(true);
                      setMenuError('');
                      setSelectedShop(shop);
                      setSearch('');
                      setCategory('all');
                      setUpdateMessage('');
                    }}
                  >
                    <span className={`cafe-avatar cafe-avatar-${index % 4}`}>{shop.slice(0, 1).toUpperCase()}</span>
                    <span className="cafe-option-name">{shop}<small>Coffee menu</small></span>
                    <span className="cafe-chevron">›</span>
                  </button>
                )) : <p className="empty-note">No cafe menus found.</p>}
              </aside>

              <div className="menu-content">
                <div className="menu-toolbar">
                  <div>
                    <h3>{selectedShop || 'Select a cafe'}</h3>
                    <p>
                      {visibleItems.length === menu.items.length
                        ? `${menu.items.length} drinks`
                        : `${visibleItems.length} of ${menu.items.length} drinks`}
                      <span className="small-divider">·</span> Updated {formatDate(menu.updated_at)}
                    </p>
                  </div>
                  <label className="search-field">
                    <span aria-hidden="true">⌕</span>
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Find a drink"
                      aria-label="Search drinks"
                    />
                  </label>
                </div>
                {menuError && <p className="notice notice-error" role="alert">{menuError}</p>}
                {updateMessage && <p className="notice notice-success" role="status">{updateMessage}</p>}
                {!menuLoading && availableCategories.length > 0 && (
                  <div className="category-bar" role="group" aria-label="Filter drinks by category">
                    <button
                      type="button"
                      className={activeCategory === 'all' ? 'category-chip active' : 'category-chip'}
                      aria-pressed={activeCategory === 'all'}
                      onClick={() => setCategory('all')}
                    >
                      All <span className="chip-count">{menu.items.length}</span>
                    </button>
                    {availableCategories.map((entry) => (
                      <button
                        type="button"
                        key={entry.id}
                        className={activeCategory === entry.id ? 'category-chip active' : 'category-chip'}
                        style={{ '--chip-color': entry.color }}
                        aria-pressed={activeCategory === entry.id}
                        onClick={() => setCategory(entry.id)}
                      >
                        <span className="chip-dot" />{entry.label} <span className="chip-count">{categoryCounts[entry.id]}</span>
                      </button>
                    ))}
                  </div>
                )}
                {menuLoading ? (
                  <div className="loading-state"><span className="spinner" /> Loading menu...</div>
                ) : (
                  <div className="table-wrap">
                    <table className="menu-table">
                      <thead>
                        <tr>
                          <th aria-sort={sortState('name')}>
                            <button type="button" className="sort-button" onClick={() => toggleSort('name')}>
                              DRINK <span className="sort-arrow" aria-hidden="true">{sort.key === 'name' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                            </button>
                          </th>
                          <th className="col-category">CATEGORY</th>
                          <th aria-sort={sortState('size')}>
                            <button type="button" className="sort-button" onClick={() => toggleSort('size')}>
                              VOLUME <span className="sort-arrow" aria-hidden="true">{sort.key === 'size' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                            </button>
                          </th>
                          <th className="price-heading" aria-sort={sortState('price')}>
                            <button type="button" className="sort-button" onClick={() => toggleSort('price')}>
                              PRICE <span className="sort-arrow" aria-hidden="true">{sort.key === 'price' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                            </button>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleItems.map((item, index) => {
                          const itemCategory = getCategory(item.category);
                          return (
                            <tr key={`${item.name}-${item.size_ml}-${index}`}>
                              <td><span className="drink-dot" style={{ background: itemCategory.color }} />{item.name}</td>
                              <td className="col-category"><span className="category-tag" style={{ '--chip-color': itemCategory.color }}>{itemCategory.label}</span></td>
                              <td>{item.size_ml ? <span className="volume-pill">{item.size_ml} ml</span> : <span className="volume-missing">Not listed</span>}</td>
                              <td className="price-cell">{Number(item.price).toLocaleString()} <span>₸</span></td>
                            </tr>
                          );
                        })}
                        {!visibleItems.length && !menuLoading && (
                          <tr><td className="empty-row" colSpan="4">
                            {menu.items.length ? 'No drinks match your search.' : 'This menu does not have any drinks yet.'}
                          </td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="volume-note"><span aria-hidden="true">ⓘ</span> Sizes show only when listed by the cafe. Missing sizes are never estimated.</div>
              </div>
            </div>

            <details className="update-panel">
              <summary><span className="update-summary-icon">＋</span><span><strong>Update this menu</strong><small>Paste a list or upload the latest cafe price file.</small></span><span className="summary-arrow">⌄</span></summary>
              <div className="update-tools">
                <div className="update-instructions">
                  <p>One drink per line. Use <code>Drink | size | price</code> to enter a volume, or leave the middle field blank when it is not listed.</p>
                  <p>Existing cafe files in the format <code>Drink — 1200 ₸</code> are also supported.</p>
                </div>
                <label className="upload-button">
                  <span aria-hidden="true">↑</span> Upload .txt
                  <input type="file" accept=".txt,text/plain" onChange={importFile} disabled={savingMenu || !selectedShop} />
                </label>
                <textarea
                  className="menu-editor"
                  value={manualText}
                  onChange={(event) => {
                    setManualText(event.target.value);
                    setUpdateMessage('');
                  }}
                  placeholder={'Americano | 250 ml | 890\nLatte | 350 ml | 1190'}
                  aria-label="Cafe menu lines"
                />
                <button className="button button-primary save-menu" onClick={() => saveMenu(manualText)} disabled={savingMenu || !selectedShop}>
                  {savingMenu ? 'Saving menu…' : 'Save menu'} <span aria-hidden="true">↗</span>
                </button>
              </div>
            </details>
          </section>
        )}

        {activeView === 'analytics' && (
          <section className="content-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">COMPARE THE POUR</p>
                <h2>Price comparison</h2>
                <p className="panel-description">See how listed prices compare for the same drink and size.</p>
              </div>
              <span className="comparison-count">{analytics.length} matched drinks</span>
            </div>
            {analyticsError && <p className="notice notice-error">{analyticsError}</p>}
            {analyticsLoading ? (
              <div className="loading-state"><span className="spinner" /> Comparing cafe menus...</div>
            ) : analytics.length ? (
              <div className="table-wrap">
                <table className="menu-table analytics-table">
                  <thead><tr>{analyticsColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>{analytics.map((row, index) => (
                    <tr key={`${row['Напиток']}-${row['Объём']}-${index}`}>
                      {analyticsColumns.map((column) => (
                        <td key={column}>{row[column] ?? '—'}{column === 'Разброс' ? ' ₸' : ''}</td>
                      ))}
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ) : !analyticsError && (
              <div className="empty-state"><span>☕</span><h3>More menus, better comparisons</h3><p>Matching drinks from at least two cafes will appear here.</p></div>
            )}
            <p className="volume-note"><span aria-hidden="true">ⓘ</span> Only exact drink-name and volume matches are compared.</p>
          </section>
        )}

        {activeView === 'chat' && (
          <section className="content-panel chat-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">STAY IN THE LOOP</p>
                <h2>Team chat</h2>
                <p className="panel-description">Share menu notes with everyone at the desk.</p>
              </div>
              <span className="live-badge"><span /> LIVE</span>
            </div>
            {chatError && <p className="notice notice-error">{chatError}</p>}
            <div className="chat-feed">
              {chatMessages.length ? chatMessages.map((message, index) => (
                <article className="chat-bubble" key={`${message.timestamp}-${index}`}>
                  <div><strong>{message.username}</strong><time>{formatDate(`${message.timestamp}Z`)}</time></div>
                  <p>{message.text}</p>
                </article>
              )) : <div className="empty-state"><span>✉</span><h3>Start the conversation</h3><p>Share a menu update or a note with your team.</p></div>}
            </div>
            <form className="chat-form" onSubmit={sendChat}>
              <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Write a message…" aria-label="Chat message" />
              <button className="button button-primary" type="submit">Send <span aria-hidden="true">↗</span></button>
            </form>
          </section>
        )}

        <footer className="footer"><span>secretbox<span className="brand-period">.</span></span><span>Made for the love of a good cup.</span></footer>
      </main>
    </div>
  );
}

export default App;